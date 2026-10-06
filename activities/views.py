from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Dict, List
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils.http import url_has_allowed_host_and_scheme
from .discovery import canonical_filters, filter_activities, facet_context
from django.http import HttpRequest, HttpResponse, QueryDict
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
    HiddenOrganizer,
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
    activity.display_when_where = f"{when} · {where}"
    activity.display_audience = activity.get_audience_display()
    activity.display_cost = activity.cost_display or (f"${activity.cost_amount:g}" if activity.cost_amount is not None and activity.cost_type == "paid" else "") or {"free": "Free", "paid": "Paid", "unknown": "Cost TBD"}.get(activity.cost_type, "Cost TBD")

    activity.compact_cost = ("Free" if activity.cost_type == "free" else
                             f"${activity.cost_amount.normalize():f}" if activity.cost_type == "paid" and activity.cost_amount is not None
                             else activity.display_cost)


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
    hidden_organizers = set(HiddenOrganizer.objects.filter(user=request.user).values_list("organizer_id", flat=True))
    hidden_condition = Q(pk__in=hidden_ids) | Q(host_id__in=hidden_organizers)
    if hidden_mode == "only":
        activities_qs = activities_qs.filter(hidden_condition)
    elif hidden_mode != "include":
        activities_qs = activities_qs.exclude(hidden_condition)
    activities_qs, nearby, filter_warning = filter_activities(activities_qs, params)
    if not nearby:
        for name in ("nearby", "lat", "lon"):
            params.pop(name, None)
    activities_qs, active_context = _filter_context(request, activities_qs, params)
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
    for activity in activities:
        _card_context(request, activity, params, hidden_organizers)
    pagination_params = params.copy()
    pagination_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "activities": activities,
        "friends": _friend_context(request.user),
        "categories": ActivityCategory.objects.all().order_by("name"),
        "active_category": category_slug,
        "filter_params": params,
        "active_context": active_context,
        "context_params": [(key, value) for key in ("organizer", "context_time", "context_place") for value in params.getlist(key)],
        "filter_warning": filter_warning,
        "facets": facet_context(params),
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
    if variant == "card":
        _decorate_activity(activity)
        _card_context(request, activity, canonical_filters(QueryDict(urlsplit(context["next_path"]).query)))
        return render(request, "activities/_card.html", context)
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


def _context_url(params, key, value=None):
    params = params.copy()
    params.pop("page", None)
    if value is None:
        params.pop(key, None)
    else:
        params[key] = str(value)
    query = params.urlencode()
    return reverse("activities:index") + ("?" + query if query else "")


def _card_context(request, activity, params, hidden_organizers=None):
    activity.context_actions = [
        {"label": "More from this organizer", "url": _context_url(params, "organizer", activity.host_id)},
        {"label": "More at this time", "url": _context_url(params, "context_time", activity.pk)}
        if activity.starts_at or activity.freetext_when.strip() else None,
        {"label": "More at this place", "url": _context_url(params, "context_place", activity.pk)}
        if activity.location_type == "online" or _place_fields(activity) else None,
        {"label": "More in this category", "url": _context_url(params, "category", activity.category.slug)}
        if activity.category else None,
    ]
    activity.context_actions = [item for item in activity.context_actions if item]
    activity.organizer_hidden = (activity.host_id in hidden_organizers if hidden_organizers is not None
                                 else HiddenOrganizer.objects.filter(user=request.user, organizer_id=activity.host_id).exists())


def _place_fields(activity):
    # Structured address wins; named locations and valid GPS points remain useful.
    from .discovery import coordinates
    fields = ["location_name", "location_address1", "location_address2", "location_city", "location_state", "location_zip"]
    values = {field + "__iexact": getattr(activity, field).strip() for field in fields if getattr(activity, field).strip()}
    if not values and coordinates(activity.location_gps):
        values = {"location_gps": activity.location_gps}
    return values


def _filter_context(request, queryset, params):
    """Context filters AND with existing facets/search; each can be cleared independently."""
    active = []
    for key in ("organizer", "context_time", "context_place"):
        value = params.get(key, "")
        if not value.isdecimal() or len(value) > 18:
            params.pop(key, None)
            continue
        if key == "organizer":
            # Resolve through activities the viewer may see, never expose private context.
            source = visible_activities(request.user).filter(host_id=int(value)).select_related("host").first()
        else:
            source = visible_activities(request.user).filter(pk=int(value)).select_related("host").first()
        if source is None:
            params.pop(key, None)
            continue
        if key == "organizer":
            queryset = queryset.filter(host_id=source.host_id)
            label = "Organizer: " + (source.organizer_name or source.host.get_full_name() or source.host.username)
        elif key == "context_time":
            if source.starts_at:
                zone = ZoneInfo(settings.PILOT_TIME_ZONE)
                day = source.starts_at.astimezone(zone).date()
                start = datetime.combine(day, time.min, tzinfo=zone)
                queryset = queryset.filter(starts_at__gte=start, starts_at__lt=start+timedelta(days=1))
                label = "Time: " + date_format(start, "D M j")
            elif source.freetext_when.strip():
                queryset = queryset.filter(starts_at__isnull=True, freetext_when__iexact=source.freetext_when.strip())
                label = "Time: " + source.freetext_when
            else:
                params.pop(key, None)
                continue
        else:
            if source.location_type == "online":
                queryset = queryset.filter(location_type__in=["online", "hybrid"])
                label = "Place: Online"
            elif _place_fields(source):
                queryset = queryset.filter(location_type__in=["in_person", "hybrid"], **_place_fields(source))
                label = "Place: " + (source.location_name or source.location_city or "Selected location")
            else:
                params.pop(key, None)
                continue
        active.append({"label": label, "clear_url": _context_url(params, key)})
    if params.get("category"):
        category = ActivityCategory.objects.filter(slug=params["category"]).first()
        if category:
            active.append({"label": "Category: " + category.name, "clear_url": _context_url(params, "category")})
    return queryset, active


@login_required
@require_POST
def hide_organizer(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    if request.POST.get("hidden") == "0":
        HiddenOrganizer.objects.filter(user=request.user, organizer_id=activity.host_id).delete()
    else:
        HiddenOrganizer.objects.get_or_create(user=request.user, organizer_id=activity.host_id)
    return redirect(_participation_next_path(request, activity))
