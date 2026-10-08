"""Free ongoing approval and enrollment; occurrence attendance stays independent."""
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (OngoingOpportunity, EnrollmentRequest, AdmissionDecision,
                     OngoingEnrollment, CohortPlace)
from .participation import locked_activity
from .visibility import visible_activities


def opportunity_for(activity):
    if not activity.is_free_ongoing:
        return None
    return getattr(activity, 'ongoing', None)


def enrollments_for(activity):
    opportunity = opportunity_for(activity)
    if not opportunity:
        return OngoingEnrollment.objects.none()
    rows = OngoingEnrollment.objects.filter(request__opportunity=opportunity,
        request__decision__result='approved', ended_at__isnull=True)
    if opportunity.capacity is not None:
        rows = rows.filter(place__released_at__isnull=True, place__isnull=False)
    return rows


def enrollment_recipients(activity):
    return set(enrollments_for(activity).values_list('request__user_id', flat=True))


def current_request(opportunity, user):
    return opportunity.requests.filter(user=user).select_related('decision', 'enrollment__place').last()


def request_place(pk, user, *, previous='', version='1'):
    with locked_activity(pk) as activity:
        if not visible_activities(user).filter(pk=pk).exists():
            raise Http404
        opportunity = opportunity_for(activity)
        if not opportunity:
            raise Http404
        if activity.is_cancelled:
            return 'This opportunity is cancelled. Requests and enrollment history are retained.'
        activity.validate_participation_policy()
        if str(version) != str(opportunity.version):
            return 'Reload the current enrollment policy before requesting a place.'
        latest = current_request(opportunity, user)
        if latest and latest.closed_at is None:
            return 'Your existing request or enrollment is retained.'
        if str(previous) != str(latest.pk if latest else ''):
            return 'Reload your current request before requesting again.'
        EnrollmentRequest.objects.create(opportunity=opportunity, user=user)
        return 'Request sent. Approval is required; no player place or meeting attendance is confirmed.'


def decide_request(pk, organizer, request_id, result, *, version='1'):
    with locked_activity(pk) as activity:
        if not activity.can_organize(organizer):
            raise Http404
        opportunity = opportunity_for(activity)
        if not opportunity:
            raise Http404
        application = get_object_or_404(opportunity.requests.select_related('user'), pk=request_id)
        if activity.is_cancelled:
            return 'This opportunity is cancelled; admission is closed. History is retained.'
        activity.validate_participation_policy()
        if str(version) != str(opportunity.version):
            return 'Reload the current enrollment policy before deciding.'
        if result not in {'approved', 'denied'}:
            raise Http404
        if application.closed_at or hasattr(application, 'decision'):
            return 'This request is closed or already decided. Its history is retained.'
        if result == 'approved':
            if not application.user.is_active or not visible_activities(application.user).filter(pk=pk).exists():
                return 'This person cannot currently access the opportunity. No decision or place changed.'
            occupied = CohortPlace.objects.filter(enrollment__request__opportunity=opportunity, released_at__isnull=True).count()
            if opportunity.capacity is not None and occupied >= opportunity.capacity:
                return 'The player pool is full. This request remains pending; no place was promised.'
        AdmissionDecision.objects.create(request=application, actor=organizer, result=result)
        if result == 'approved':
            enrollment = OngoingEnrollment.objects.create(request=application)
            if opportunity.capacity is not None:
                CohortPlace.objects.create(enrollment=enrollment)
            return 'Approved and enrolled. A free player place is secured; meeting attendance remains separate.'
        application.closed_at = timezone.now()
        application.save(update_fields=['closed_at'])
        return 'Request denied. No player place was allocated; request and decision history are retained.'


def withdraw_request(pk, user, request_id, *, version='1'):
    with locked_activity(pk) as activity:
        if not visible_activities(user).filter(pk=pk).exists():
            raise Http404
        opportunity = opportunity_for(activity)
        if not opportunity:
            raise Http404
        application = get_object_or_404(opportunity.requests, pk=request_id, user=user)
        if activity.is_cancelled:
            return 'This opportunity is cancelled. Enrollment and request history are retained.'
        if str(version) != str(opportunity.version):
            return 'Reload the current enrollment policy before withdrawing.'
        if application.closed_at:
            return 'This request is already closed; its history is retained.'
        now = timezone.now()
        application.closed_at = application.withdrawn_at = now
        application.save(update_fields=['closed_at', 'withdrawn_at'])
        enrollment = getattr(application, 'enrollment', None)
        if enrollment:
            enrollment.ended_at = now
            enrollment.save(update_fields=['ended_at'])
            place = getattr(enrollment, 'place', None)
            if place:
                place.released_at = now
                place.save(update_fields=['released_at'])
        return 'Withdrawn. Your ongoing player place is released; meeting responses and history are unchanged.'


def enrollment_context(request, activity, *, organizer=False):
    opportunity = opportunity_for(activity)
    if not opportunity:
        return {}
    own = current_request(opportunity, request.user)
    state = ''
    if own:
        decision = getattr(own, 'decision', None)
        if own.withdrawn_at:
            state = 'Withdrawn'
        elif decision and decision.result == 'denied':
            state = 'Request denied'
        elif enrollments_for(activity).filter(request=own).exists():
            state = 'Enrolled'
        else:
            state = 'Request sent'
    rows = opportunity.requests.select_related('user__profile', 'decision__actor__profile', 'enrollment__place')
    history = list(rows if organizer else rows.filter(user=request.user))
    meetings = opportunity.meetings.filter(pk__in=visible_activities(request.user).values('pk')).order_by('-created_at')
    return {'ongoing': opportunity, 'enrollment_request': own, 'enrollment_state': state,
        'enrollment_history': history, 'enrollment_count': enrollments_for(activity).count(),
        'enrollment_pending': opportunity.requests.filter(closed_at__isnull=True, decision__isnull=True).count() if organizer else None,
        'enrollment_meetings': meetings}


@login_required
@require_POST
def request_enrollment(request, pk):
    notice = request_place(pk, request.user, previous=request.POST.get('request', ''), version=request.POST.get('policy', ''))
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    from .views import _render_join_region
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def withdraw_enrollment(request, pk):
    application = request.POST.get('request', '')
    if not application.isdigit():
        raise Http404
    notice = withdraw_request(pk, request.user, int(application), version=request.POST.get('policy', ''))
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    from .views import _render_join_region
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def decide_enrollment(request, pk, request_pk):
    notice = decide_request(pk, request.user, request_pk, request.POST.get('decision'), version=request.POST.get('policy', ''))
    messages.info(request, notice)
    return redirect(reverse('activities:roster', args=[pk]))
