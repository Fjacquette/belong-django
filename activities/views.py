from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import ActivityForm
from .visibility import visible_activities
from .models import (
    Activity,
    ActivityCategory,
    ActivityLocationType,
    ActivityResponse,
    ActivityResponseStatus,
    ActivityVisibility,
)
from social.models import Friendship, UserProfile

PAGE_SIZE = 12
RESPONSE_LABELS = dict(ActivityResponseStatus.choices)


def _decorate_activity(activity: Activity) -> None:
    category = activity.category
    activity.display_color_primary = (
        activity.color_primary
        or (category.color_primary if category and category.color_primary else "#843A96")
    )
    activity.display_color_secondary = (
        activity.color_secondary
        or (category.color_secondary if category and category.color_secondary else "#5C2969")
    )
    activity.display_category_name = category.name if category else "Belong"

    if activity.headline:
        activity.display_subline = activity.headline
    else:
        meta_parts = []
        if activity.freetext_when:
            meta_parts.append(activity.freetext_when)
        if activity.location_city:
            location = activity.location_city
            if activity.location_state:
                location = f"{location}, {activity.location_state}"
            meta_parts.append(location)
        elif activity.location_type == ActivityLocationType.ONLINE:
            meta_parts.append("Online")
        activity.display_subline = " • ".join(meta_parts)


def _friend_context(user) -> List[Dict[str, object]]:
    if not user.is_authenticated:
        return []

    friendships = Friendship.objects.filter(Q(user_a=user) | Q(user_b=user))
    friend_ids = set()
    for friendship in friendships:
        other_id = friendship.user_a_id if friendship.user_b_id == user.id else friendship.user_b_id
        friend_ids.add(other_id)

    if not friend_ids:
        return []

    profiles = (
        UserProfile.objects.select_related("user")
        .filter(user_id__in=friend_ids, is_visible=True)
        .order_by("-status_updated_at")
    )
    now = timezone.now()
    result = []
    for profile in profiles:
        last_active = profile.last_active_at or profile.status_updated_at
        result.append(
            {
                "user": profile.user,
                "profile": profile,
                "status": profile.status_text,
                "last_active": last_active,
                "is_recent": last_active and (now - last_active) <= timedelta(minutes=20),
            }
        )
    return result


def _build_join_context(request: HttpRequest, activity: Activity) -> Dict[str, object]:
    # Reuse discovery's prefetched responses; keep interest distinct from commitment.
    responses = list(activity.responses.all())
    interested_count = sum(r.status == ActivityResponseStatus.INTERESTED for r in responses)
    committed_count = sum(r.status == ActivityResponseStatus.COMMITTED for r in responses)
    attendee_count = interested_count + committed_count
    current_response = next((r for r in responses if r.user_id == request.user.pk), None)

    response_options = []
    for value in activity.active_responses():
        response_options.append(
            {
                "value": value,
                "label": RESPONSE_LABELS.get(value, value.replace("_", " ").title()),
            }
        )

    current_status = current_response.status if current_response else None

    activity.is_joined = current_response is not None
    activity.attendee_count = attendee_count

    return {
        "activity": activity,
        "attendee_count": attendee_count,
        "interested_count": interested_count,
        "committed_count": committed_count,
        "joined": activity.is_joined,
        "current_status": current_status,
        "current_status_label": RESPONSE_LABELS.get(current_status, ""),
        "response_options": response_options,
        "card_response_options": [
            option
            for value in (ActivityResponseStatus.INTERESTED, ActivityResponseStatus.COMMITTED)
            for option in response_options
            if option["value"] == value
        ],
    }


def _annotate_join_data(request: HttpRequest, activities: List[Activity]) -> None:
    for activity in activities:
        _decorate_activity(activity)
        context = _build_join_context(request, activity)
        activity.j_attendee_count = context["attendee_count"]
        activity.j_interested_count = context["interested_count"]
        activity.j_committed_count = context["committed_count"]
        activity.j_joined = context["joined"]
        activity.j_current_status = context["current_status"]
        activity.j_current_status_label = context["current_status_label"]
        activity.j_response_options = context["response_options"]
        activity.j_card_response_options = context["card_response_options"]


@login_required
def index(request: HttpRequest) -> HttpResponse:
    activities_qs = visible_activities(request.user).select_related("host", "category").prefetch_related("responses").annotate(
        attendee_count=Count(
            "responses",
            filter=Q(
                responses__status__in=[
                    ActivityResponseStatus.INTERESTED,
                    ActivityResponseStatus.COMMITTED,
                ]
            ),
        )
    )

    category_slug = request.GET.get("category")
    if category_slug:
        activities_qs = activities_qs.filter(category__slug=category_slug)

    query = request.GET.get("q")
    if query:
        activities_qs = activities_qs.filter(
            Q(title__icontains=query)
            | Q(headline__icontains=query)
            | Q(summary__icontains=query)
            | Q(description__icontains=query)
        )

    activities_qs = activities_qs.order_by("-starts_at", "-created_at")

    paginator = Paginator(activities_qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    activities = list(page_obj.object_list)
    _annotate_join_data(request, activities)

    context = {
        "page_obj": page_obj,
        "activities": activities,
        "friends": _friend_context(request.user),
        "categories": ActivityCategory.objects.all().order_by("name"),
        "active_category": category_slug,
        "query": query,
    }
    return render(request, "activities/index.html", context)


@login_required
def category_explore(request: HttpRequest) -> HttpResponse:
    categories = ActivityCategory.objects.all().order_by("name")
    context = {
        "categories": categories,
        "friends": _friend_context(request.user),
    }
    return render(request, "activities/categories.html", context)


@login_required
def detail(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(
        visible_activities(request.user).select_related("host", "category")
        .prefetch_related("responses")
        .annotate(
            attendee_count=Count(
                "responses",
                filter=Q(
                    responses__status__in=[
                        ActivityResponseStatus.INTERESTED,
                        ActivityResponseStatus.COMMITTED,
                    ]
                ),
            )
        ),
        pk=pk,
    )

    _decorate_activity(activity)
    join_context = _build_join_context(request, activity)

    context = {
        "activity": activity,
        "join_context": join_context,
        "friends": _friend_context(request.user),
    }
    return render(request, "activities/detail.html", context)


@login_required
def create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity: Activity = form.save(commit=False)
            activity.host = request.user
            activity.save()
            messages.success(request, "Activity created!")
            return redirect("activities:detail", pk=activity.pk)
    else:
        form = ActivityForm()

    return render(request, "activities/form.html", {"form": form})


@login_required
@require_POST
def respond(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    status = request.POST.get("status")
    allowed = activity.active_responses()
    if not status or status not in allowed:
        return _render_join_region(request, activity)

    ActivityResponse.objects.update_or_create(
        user=request.user,
        activity=activity,
        defaults={"status": status},
    )
    return _render_join_region(request, activity)


@login_required
@require_POST
def join(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    allowed_statuses = activity.active_responses()
    default_status = next(
        (status for status in (ActivityResponseStatus.INTERESTED, ActivityResponseStatus.COMMITTED)
         if status in allowed_statuses), None,
    )
    if default_status is None:
        return _render_join_region(request, activity)
    ActivityResponse.objects.update_or_create(
        user=request.user,
        activity=activity,
        defaults={"status": default_status},
    )
    return _render_join_region(request, activity)


@login_required
@require_POST
def leave(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    ActivityResponse.objects.filter(user=request.user, activity=activity).delete()
    return _render_join_region(request, activity)


def _render_join_region(request: HttpRequest, activity: Activity) -> HttpResponse:
    variant = "detail" if request.POST.get("variant") == "detail" else "card"
    # UI forms also work when HTMX is unavailable. Preserve the existing fragment API.
    if "variant" in request.POST and request.headers.get("HX-Request") != "true":
        if variant == "detail":
            return redirect("activities:detail", pk=activity.pk)
        return redirect("activities:index")
    context = _build_join_context(request, activity)
    context["variant"] = variant
    return render(request, "activities/_join_region.html", context)
