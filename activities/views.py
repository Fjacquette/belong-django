from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils.http import url_has_allowed_host_and_scheme
from .discovery import canonical_filters, filter_activities
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.formats import date_format

from .forms import ActivityForm
from .visibility import visible_activities
from .models import (
    Activity,
    ActivityCostType,
    HiddenActivity,
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

    when = date_format(timezone.localtime(activity.starts_at), "D M j, g:i A") if activity.starts_at else activity.freetext_when or "Date TBD"
    if when.strip().lower() in {"tbd", "tba"}:
        when = "Date TBD"
    if activity.location_type == ActivityLocationType.ONLINE:
        where = "Online"
    else:
        where = activity.location_name or ", ".join(filter(None, [activity.location_city, activity.location_state])) or "Location TBD"
        if activity.location_type == ActivityLocationType.HYBRID:
            where += " / Online"
    activity.display_subline = activity.headline
    activity.display_when_where = f"{when} · {where}"
    activity.display_audience = activity.get_audience_display()
    activity.display_cost = activity.cost_display or {"free": "Free", "paid": "Paid", "unknown": "Cost TBD"}.get(activity.cost_type, "Cost TBD")


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
        last_active = profile.last_active_at
        age = (now - last_active) if last_active else None
        presence = "Active" if age is not None and age <= timedelta(minutes=5) else "Idle" if age is not None and age <= timedelta(minutes=30) else "Offline"
        result.append(
            {
                "user": profile.user,
                "profile": profile,
                "status": profile.status_text,
                "last_active": last_active,
                "presence": presence,
                "presence_help": "Authenticated activity within 5 minutes" if presence == "Active" else "Authenticated activity within 30 minutes" if presence == "Idle" else "No authenticated activity within 30 minutes",
            }
        )
    return result


def _participation_next_path(request: HttpRequest, activity: Activity) -> str:
    destination = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()):
        return destination
    if request.POST.get("variant") == "detail":
        return reverse("activities:detail", args=[activity.pk])
    return reverse("activities:index")


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
    card_response_options = response_options[:2]
    card_current_status_label = (
        RESPONSE_LABELS.get(current_status, "")
        if current_status and current_status not in [option["value"] for option in card_response_options]
        else ""
    )

    activity.is_hidden = HiddenActivity.objects.filter(user=request.user, activity=activity).exists()
    activity.is_joined = current_response is not None
    activity.attendee_count = attendee_count

    return {
        "activity": activity,
        "attendee_count": attendee_count,
        "response_count": len(responses),
        "response_counts_label": "; ".join(
            f"{label}: {sum(r.status == value for r in responses)}"
            for value, label in ActivityResponseStatus.choices
            if value in activity.active_responses() or any(r.status == value for r in responses)
        ),
        "interested_count": interested_count,
        "committed_count": committed_count,
        "joined": activity.is_joined,
        "current_status": current_status,
        "current_status_label": RESPONSE_LABELS.get(current_status, ""),
        "response_options": response_options,
        "card_response_options": card_response_options,
        "card_current_status_label": card_current_status_label,
        "next_path": _participation_next_path(request, activity) if request.method == "POST" else request.get_full_path(),
    }


def _annotate_join_data(request: HttpRequest, activities: List[Activity]) -> None:
    for activity in activities:
        _decorate_activity(activity)
        context = _build_join_context(request, activity)
        activity.j_attendee_count = context["attendee_count"]
        activity.j_response_count = context["response_count"]
        activity.j_response_counts_label = context["response_counts_label"]
        activity.j_interested_count = context["interested_count"]
        activity.j_committed_count = context["committed_count"]
        activity.j_joined = context["joined"]
        activity.j_current_status = context["current_status"]
        activity.j_current_status_label = context["current_status_label"]
        activity.j_response_options = context["response_options"]
        activity.j_card_response_options = context["card_response_options"]
        activity.j_card_current_status_label = context["card_current_status_label"]


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

    params = canonical_filters(request.GET)
    hidden_mode = params.get("hidden", "exclude")
    hidden_ids = HiddenActivity.objects.filter(user=request.user).values("activity_id")
    if hidden_mode == "only":
        activities_qs = activities_qs.filter(pk__in=hidden_ids)
    elif hidden_mode != "include":
        activities_qs = activities_qs.exclude(pk__in=hidden_ids)
    activities_qs, nearby, filter_warning = filter_activities(activities_qs, params)
    if not nearby:
        for name in ("nearby", "lat", "lon"):
            params.pop(name, None)
    category_slug = params.get("category")
    if category_slug:
        activities_qs = activities_qs.filter(category__slug=category_slug)

    query = params.get("q")
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
    hidden_set = set(hidden_ids.values_list("activity_id", flat=True))
    for activity in activities:
        activity.is_hidden = activity.pk in hidden_set
    pagination_params = params.copy()
    pagination_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "activities": activities,
        "friends": _friend_context(request.user),
        "categories": ActivityCategory.objects.all().order_by("name"),
        "active_category": category_slug,
        "filter_params": params,
        "filter_warning": filter_warning,
        "quick_filters": [{"name": name, "label": label, "active": params.get(dimension) == value}
                          for name, label, dimension, value in [("today", "Today", "timing", "today"), ("nearby", "Nearby", "nearby", "1"), ("online", "Online", "location", "online_capable"), ("free", "Free", "cost", "free")]],
        "location_choices": [("online_capable", "Online or hybrid"), *ActivityLocationType.choices],
        "cost_choices": ActivityCostType.choices,
        "pagination_query": pagination_params.urlencode(),
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
        visible_activities(request.user).select_related("host", "category", "group")
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
        "show_group": activity.group and activity.group.can_view(request.user),
    }
    return render(request, "activities/detail.html", context)


@login_required
def create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ActivityForm(request.POST, user=request.user)
        if form.is_valid():
            activity: Activity = form.save(commit=False)
            activity.host = request.user
            activity.save()
            messages.success(request, "Activity created!")
            return redirect("activities:detail", pk=activity.pk)
    else:
        form = ActivityForm(user=request.user, initial={"group": request.GET.get("group")})

    return render(request, "activities/form.html", {"form": form})


@login_required
@require_POST
def respond(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    status = request.POST.get("status")
    allowed = activity.active_responses()
    if not status or status not in allowed:
        return _render_join_region(request, activity)

    existing = ActivityResponse.objects.filter(user=request.user, activity=activity).first()
    if existing and existing.status == status:
        existing.delete()
    else:
        ActivityResponse.objects.update_or_create(user=request.user, activity=activity, defaults={"status": status})
    return _render_join_region(request, activity)


@login_required
@require_POST
def join(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    allowed_statuses = activity.active_responses()
    default_status = next(iter(allowed_statuses), None)
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
        return redirect(_participation_next_path(request, activity))
    context = _build_join_context(request, activity)
    context["variant"] = variant
    return render(request, "activities/_join_region.html", context)


@login_required
@require_POST
def hide(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    if request.POST.get("hidden") == "0":
        HiddenActivity.objects.filter(user=request.user, activity=activity).delete()
    else:
        HiddenActivity.objects.get_or_create(user=request.user, activity=activity)
    destination = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()):
        destination = reverse("activities:index")
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(headers={"HX-Refresh": "true"})
    return redirect(destination)
