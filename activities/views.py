from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Dict, List
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme
from .discovery import canonical_filters, filter_activities, facet_context
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.formats import date_format

from .forms import ActivityForm, CancelActivityForm
from .visibility import visible_activities
from .announcements import update_context
from .invitations import is_invited, with_invitation_state, RSVP_LABELS
from .group_offers import current_offer
from .polls import responses_for, poll_context, create_poll
from .enrollment import enrollment_context
from .registration import registration_context
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
    current_response_values,
    DEFAULT_RESPONSE_CHOICES,
)
from social.models import Friendship, UserProfile

PAGE_SIZE = 12
RESPONSE_LABELS = dict(ActivityResponseStatus.choices)
CARD_RESPONSE_LABELS = {'committed': 'Going', 'declined': "Can't make it", 'question': 'Have a question',
                        'more': 'Tell me more', 'vote': 'Vote on details', 'interested': 'Past response'}


def _decorate_activity(activity: Activity) -> None:
    activity.display_title = f"Cancelled: {activity.title}" if activity.is_cancelled else activity.title
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
    activity.display_when = when
    activity.display_where = where
    from .card_style import header_gradient, response_accent
    activity.card_accent = response_accent(activity.display_color_primary)
    activity.card_header_left, activity.card_header_right = header_gradient(
        activity.display_color_primary, activity.display_color_secondary)
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
    responses = responses_for(activity)
    interested_count = sum(r.status == ActivityResponseStatus.INTERESTED for r in responses)
    committed_count = sum(r.status == ActivityResponseStatus.COMMITTED for r in responses)
    attendee_count = committed_count
    current_response = next((r for r in responses if r.user_id == request.user.pk), None)

    capacity_reached = activity.capacity is not None and committed_count >= activity.capacity
    invited = bool(is_invited(activity, request.user))
    response_values = list(dict.fromkeys((list(RSVP_LABELS) if invited and activity.uses_legacy_participation else []) + activity.active_responses()))
    response_options = []
    for value in response_values if activity.uses_legacy_participation else []:
        response_options.append(
            {
                "value": value,
                "status": value,
                "field": "status",
                "label": (RSVP_LABELS.get(value) if invited else None) or RESPONSE_LABELS.get(value, value.replace("_", " ").title()),
                "disabled": value == ActivityResponseStatus.COMMITTED and capacity_reached and (not current_response or current_response.status != value),
            }
        )
    if not activity.uses_legacy_participation:
        response_options = activity.participation_options()
        for option in response_options:
            option['disabled'] = option['status'] == 'committed' and capacity_reached and (not current_response or current_response.status != 'committed')

    current_status = current_response.status if current_response else None
    card_response_options = response_options[:2] if invited and not activity.is_cancelled else []
    card_current_status_label = CARD_RESPONSE_LABELS.get(current_status, 'Previous response') if current_status else ''
    if activity.participation_options() and current_status:
        card_current_status_label = activity.response_label(current_status)
    card_unmatched_response = bool(activity.uses_legacy_participation and invited and current_status and current_status not in RSVP_LABELS)

    if not hasattr(activity, "is_hidden"):
        activity.is_hidden = HiddenActivity.objects.filter(user=request.user, activity=activity).exists()
    activity.is_joined = current_response is not None
    activity.attendee_count = attendee_count

    enrollment = enrollment_context(request, activity)
    activity.j_enrollment_state = enrollment.get('enrollment_state', '')
    registration = registration_context(request, activity)
    activity.j_registration_state = registration.get('registration_state', '')
    return {
        "activity": activity,
        **poll_context(request,activity),
        **enrollment,
        **registration,
        "invited": invited,
        "attendee_count": attendee_count,
        "response_count": len(responses),
        "capacity_reached": capacity_reached,
        "response_counts_label": "; ".join(
            f"{activity.response_label(value)}: {sum(r.status == value for r in responses)}"
            for value, label in ActivityResponseStatus.choices
            if value in activity.active_responses() or any(r.status == value for r in responses)
        ),
        "interested_count": interested_count,
        "committed_count": committed_count,
        "joined": activity.is_joined,
        "current_status": current_status,
        "current_status_label": activity.response_label(current_status, invited=invited) if current_status else '',
        "response_options": response_options,
        "card_response_options": card_response_options,
        "card_current_status_label": card_current_status_label,
        "card_unmatched_response": card_unmatched_response,
        "next_path": _participation_next_path(request, activity) if request.method == "POST" else request.get_full_path(),
    }


def _annotate_join_data(request: HttpRequest, activities: List[Activity]) -> None:
    for activity in activities:
        _decorate_activity(activity)
        context = _build_join_context(request, activity)
        activity.j_invited = context["invited"]
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
        activity.j_card_unmatched_response = context['card_unmatched_response']
        activity.j_poll_answered = context.get('poll_answered', False)
        activity.j_enrollment_state = context.get('enrollment_state', '')


@login_required
def index(request: HttpRequest) -> HttpResponse:
    activities_qs = visible_activities(request.user).select_related("host__profile__avatar_image", "category").prefetch_related("responses")

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

    activities = list(with_invitation_state(page_obj.object_list, request.user))
    hidden_set = set(hidden_ids.values_list("activity_id", flat=True))
    for activity in activities:
        activity.is_hidden = activity.pk in hidden_set
    _annotate_join_data(request, activities)
    for activity in activities:
        _card_context(request, activity, params, hidden_organizers)
    pagination_params = params.copy()
    pagination_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "group_join_offer": current_offer(request.user),
        "offer_next_path": request.get_full_path(),
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
        visible_activities(request.user).select_related("host__profile__avatar_image", "category", "group").prefetch_related("responses"),
        pk=pk,
    )

    _decorate_activity(activity)
    join_context = _build_join_context(request, activity)
    discover_path = request.GET.get('discover', '')
    if (not url_has_allowed_host_and_scheme(discover_path, {request.get_host()}, require_https=request.is_secure())
            or urlsplit(discover_path).path != reverse('activities:index')):
        discover_path = reverse('activities:index')

    context = {
        "activity": activity,
        "group_join_offer": current_offer(request.user, activity),
        "offer_next_path": request.get_full_path(),
        "discover_path": discover_path,
        "join_context": join_context,
        "friends": _friend_context(request.user),
        "can_organize": activity.can_organize(request.user),
        "show_group": activity.group and activity.group.can_view(request.user),
        "show_series": activity.series and activity.series.can_organize(request.user),
    }
    context.update(update_context(request, activity, organizer=activity.can_organize(request.user)))
    context.update(poll_context(request,activity))
    context.update(enrollment_context(request,activity))
    context.update(registration_context(request,activity))
    origin = activity.ongoing_opportunity
    context['meeting_origin'] = origin if origin and visible_activities(request.user).filter(pk=origin.activity_id).exists() else None
    return render(request, "activities/detail.html", context)


@login_required
def create(request: HttpRequest) -> HttpResponse:
    from .series import occurrence_initial
    from .models import ActivitySeries
    series = None
    initial = {}
    opportunity = None
    opportunity_id = request.GET.get('opportunity')
    if opportunity_id:
        from .models import OngoingOpportunity
        if not opportunity_id.isdigit() or request.GET.get('series'):
            raise Http404
        opportunity = get_object_or_404(OngoingOpportunity.objects.select_related('activity__group'), pk=opportunity_id)
        if not opportunity.activity.can_organize(request.user) or opportunity.activity.is_cancelled:
            raise Http404
        initial = {'title': opportunity.activity.title, 'cost_type': 'free', 'audience': opportunity.activity.audience,
            'participation_config': {'version': 2, 'pattern': 'scheduled', 'actions': ['view_details', 'confirm_attendance', 'decline_attendance']}}
    series_id = request.GET.get('series')
    if series_id:
        if not series_id.isdigit():
            raise Http404
        series = _series_for(request.user, series_id)
        initial = occurrence_initial(series)
    group = series.group if series else opportunity.activity.group if opportunity else None
    group_id = request.GET.get('group')
    if group_id:
        if not group_id.isdigit():
            raise Http404
        choices = ActivityForm(user=request.user).fields['group'].queryset
        selected = get_object_or_404(choices, pk=group_id)
        if opportunity and opportunity.activity.group_id and selected.pk != opportunity.activity.group_id:
            raise Http404
        if series and series.group_id and selected.pk != series.group_id:
            raise Http404
        group = selected
    if request.method == 'POST':
        form = ActivityForm(request.POST, user=request.user, context_group=group, context_series=series, context_opportunity=opportunity, initial=initial)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.host = request.user
            activity.ongoing_opportunity = opportunity
            from django.db import transaction
            from .participation import locked_activity
            with (locked_activity(opportunity.activity_id) if opportunity else transaction.atomic()) as source:
                if opportunity and (source.is_cancelled or not source.can_organize(request.user)):
                    raise Http404
                activity.save()
                if activity.is_date_planning:
                    create_poll(activity,[form.cleaned_data[f'poll_date_{n}'] for n in range(1,4)])
                if activity.is_registration:
                    from .models import RegistrationTarget
                    RegistrationTarget.objects.create(activity=activity, **form.cleaned_data['registration_terms'])
                if activity.is_free_ongoing:
                    from .models import OngoingOpportunity
                    OngoingOpportunity.objects.create(activity=activity, capacity=form.cleaned_data.get('cohort_capacity'))
            messages.success(request, 'Activity created!')
            return redirect('activities:detail', pk=activity.pk)
    else:
        form = ActivityForm(user=request.user, context_group=group, context_series=series, context_opportunity=opportunity, initial=initial)
    groups = list(form.fields['group'].queryset.select_related('default_activity_image'))
    series_choices = ActivitySeries.objects.filter(Q(owner=request.user, group__isnull=True) | Q(group__in=groups)).distinct()
    if group:
        series_choices = series_choices.filter(group=group)
    return render(request, 'activities/form.html', {'form': form, 'context_group': group, 'context_series': series, 'context_opportunity': opportunity, 'series_choices': series_choices,
                  'group_defaults': {str(g.pk): {'name': g.name, 'image': str((series.header_image_id if series else None) or g.default_activity_image_id or '')} for g in groups},
                  'suppress_create': True})


@login_required
@require_POST
def respond(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    from .participation import change_response
    notice = change_response(activity.pk, request.user, request.POST.get('status', ''), action=request.POST.get('action'),
        confirmation_round=request.POST.get('confirmation_round'),toggle=True)
    activity.refresh_from_db()
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def join(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    from .participation import change_response
    notice = change_response(activity.pk, request.user,confirmation_round=request.POST.get('confirmation_round'))
    activity.refresh_from_db()
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def leave(request: HttpRequest, pk: int) -> HttpResponse:
    activity = get_object_or_404(visible_activities(request.user).select_related("host"), pk=pk)
    from .participation import change_response
    notice = change_response(activity.pk, request.user,confirmation_round=request.POST.get('confirmation_round'),remove=True)
    activity.refresh_from_db()
    return _render_join_region(request, activity, notice)


def _render_join_region(request: HttpRequest, activity: Activity, notice="") -> HttpResponse:
    variant = "detail" if request.POST.get("variant") == "detail" else "card"
    # UI forms also work when HTMX is unavailable. Preserve the existing fragment API.
    if "variant" in request.POST and request.headers.get("HX-Request") != "true":
        if notice:
            messages.info(request, notice)
        return redirect(_participation_next_path(request, activity))
    context = _build_join_context(request, activity)
    context["variant"] = variant
    context["participation_notice"] = notice
    context['group_join_offer'] = current_offer(request.user, activity)
    context['offer_next_path'] = context['next_path']
    context['offer_oob'] = request.headers.get('HX-Request') == 'true'
    if variant == "card":
        _decorate_activity(activity)
        _card_context(request, activity, canonical_filters(QueryDict(urlsplit(context["next_path"]).query)))
    return render(request, "activities/_participation_result.html", context)


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
            label = "Organizer: " + (source.organizer_display_name)
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


def _series_for(user, pk):
    from .models import ActivitySeries
    series = get_object_or_404(ActivitySeries.objects.select_related('group', 'group__default_activity_image', 'owner', 'header_image'), pk=pk)
    if not series.can_organize(user):
        raise Http404
    return series


@login_required
def series_create(request):
    from .forms import ActivitySeriesForm
    group = None
    group_id = request.GET.get('group')
    if group_id:
        if not group_id.isdigit():
            raise Http404
        group = get_object_or_404(ActivityForm(user=request.user).fields['group'].queryset, pk=group_id)
    form = ActivitySeriesForm(request.POST if request.method == 'POST' else None, user=request.user, context_group=group)
    if request.method == 'POST' and form.is_valid():
        series = form.save(commit=False)
        series.owner = request.user
        series.save()
        return redirect(series)
    return render(request, 'activities/series_form.html', {'form': form, 'context_group': group, 'suppress_create': True})


@login_required
def series_edit(request, pk):
    from .forms import ActivitySeriesForm
    series = _series_for(request.user, pk)
    form = ActivitySeriesForm(request.POST if request.method == 'POST' else None, instance=series, user=request.user, context_group=series.group)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect(series)
    return render(request, 'activities/series_form.html', {'form': form, 'series': series, 'context_group': series.group, 'suppress_create': True})


@login_required
def series_detail(request, pk):
    series = _series_for(request.user, pk)
    choices = dict(ActivityResponseStatus.choices)
    return render(request, 'activities/series_detail.html', {'series': series,
        'response_labels': [choices[c] for c in (current_response_values(series.available_responses) if series.available_responses else DEFAULT_RESPONSE_CHOICES)] if series.uses_legacy_participation else [],
        'occurrences': Activity.objects.filter(series=series).filter(Q(host=request.user) | (Q(group_id=series.group_id) if series.group_id else Q(pk__in=[]))),
    })


def _organizer_activity(user, pk):
    activity = get_object_or_404(Activity.objects.select_related('group', 'series', 'host__profile'), pk=pk)
    if not activity.can_organize(user):
        raise Http404
    return activity


@login_required
def roster(request, pk):
    return _render_roster(request, _organizer_activity(request.user, pk))


def _render_roster(request, activity, cancel_form=None, invite_form=None, group_invite_form=None, email_invite_form=None):
    from .invitations import DirectInviteForm, GroupInviteForm, EmailInviteForm
    _decorate_activity(activity)
    responses = responses_for(activity) if activity.is_date_planning else list(activity.responses.select_related('user__profile').order_by('created_at', 'pk'))
    for response in responses:
        response.participation_label = activity.response_label(response.status)
    counts = [{'label': activity.response_label(value), 'count': sum(r.status == value for r in responses)}
              for value, label in ActivityResponseStatus.choices
              if value in activity.active_responses() or any(r.status == value for r in responses)]
    return render(request, 'activities/roster.html', {
        'email_invite_form': email_invite_form if email_invite_form is not None else EmailInviteForm(),
        'email_invitations': activity.email_invitations.all(),
        'can_send_email_invitations': request.user.profile.email_verified_at and not request.user.profile.outbound_mail_suspended and not activity.is_cancelled,
        'direct_invitees': activity.direct_invitations.select_related('user__profile'),
        'invite_form': invite_form if invite_form is not None else DirectInviteForm(activity=activity, organizer=request.user),
        'group_invite_form': group_invite_form if group_invite_form is not None else GroupInviteForm(activity=activity, initial={'invite_group_members': activity.invite_group_members}),
        **update_context(request, activity, organizer=True),
        **poll_context(request,activity,organizer=True),
        **enrollment_context(request,activity,organizer=True),
        **registration_context(request,activity,organizer=True),
        'activity': activity, 'responses': responses, 'counts': counts,
        'committed_count': sum(r.status == ActivityResponseStatus.COMMITTED for r in responses),
        'cancel_form': cancel_form if cancel_form is not None else CancelActivityForm(), 'suppress_create': True,
        'can_view_details': visible_activities(request.user).filter(pk=activity.pk).exists(),
        'show_series': activity.series and activity.series.can_organize(request.user),
    })


@login_required
@require_POST
def cancel(request, pk):
    activity = _organizer_activity(request.user, pk)
    form = CancelActivityForm(request.POST)
    if not form.is_valid():
        return _render_roster(request, activity, form)
    from .participation import cancel_activity
    if not cancel_activity(activity.pk, request.user, form.cleaned_data['reason']):
        raise Http404
    return redirect('activities:roster', pk=pk)


@login_required
@require_POST
def manage_invitations(request, pk):
    from .invitations import DirectInviteForm, GroupInviteForm
    from .models import ActivityInvitation
    from .participation import locked_activity
    _organizer_activity(request.user, pk)
    with locked_activity(pk) as activity:
        if not activity.can_organize(request.user):
            raise Http404
        action = request.POST.get('action')
        if action == 'group':
            form = GroupInviteForm(request.POST, activity=activity)
            if not form.is_valid():
                return _render_roster(request, activity, group_invite_form=form)
            activity.invite_group_members = form.cleaned_data['invite_group_members']
            activity.save(update_fields=['invite_group_members', 'updated_at'])
        elif action == 'add':
            form = DirectInviteForm(request.POST, activity=activity, organizer=request.user)
            if not form.is_valid():
                return _render_roster(request, activity, invite_form=form)
            ActivityInvitation.objects.get_or_create(activity=activity, user=form.cleaned_data['invitee'], defaults={'invited_by': request.user})
        elif action == 'remove':
            invitation_id = request.POST.get('invitation', '')
            if not invitation_id.isdigit():
                raise Http404
            invitation = get_object_or_404(activity.direct_invitations, pk=invitation_id)
            invitation.delete()
        else:
            raise Http404
    return redirect('activities:roster', pk=pk)
