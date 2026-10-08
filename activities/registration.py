"""D2 eligibility and free registration. Paid quotes cannot be fulfilled here."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import RegistrationRequest, RegistrationAdmission, FreeRegistration, RegistrationPlace
from .participation import locked_activity
from .visibility import visible_activities
from .invitations import is_invited


def target_for(activity):
    return getattr(activity, 'registration_target', None) if activity.is_registration else None


def registrations_for(activity):
    target = target_for(activity)
    if not target or target.amount != 0:
        return FreeRegistration.objects.none()
    rows = FreeRegistration.objects.filter(request__target=target, request__closed_at__isnull=True, ended_at__isnull=True)
    if target.admission == 'request':
        rows = rows.filter(request__decision__result='approved')
    if target.capacity is not None:
        rows = rows.filter(place__isnull=False, place__released_at__isnull=True)
    # Secured entitlements survive invitation loss and cancellation, for history
    # and cancellation snapshots. Access/lifecycle qualify their presentation.
    return rows


def eligible(application, activity):
    target = application.target
    if application.closed_at or not application.user.is_active:
        return False
    if not visible_activities(application.user).filter(pk=activity.pk).exists():
        return False
    if target.admission == 'request':
        return getattr(getattr(application, 'decision', None), 'result', None) == 'approved'
    return target.admission == 'open' or is_invited(activity, application.user)


def occupied(target):
    return RegistrationPlace.objects.filter(confirmation__request__target=target, released_at__isnull=True).count()


def full(target):
    from .reservations import pool_for, used
    pool = pool_for(target)
    if pool:
        return used(pool) >= pool.capacity
    return target.capacity is not None and occupied(target) >= target.capacity


def secure_free(application):
    confirmation = FreeRegistration.objects.create(request=application)
    if application.target.capacity is not None:
        RegistrationPlace.objects.create(confirmation=confirmation)


def current_request(target, user):
    return target.requests.filter(user=user).select_related('target', 'user', 'decision', 'confirmation__place').last()


def mutate(pk, actor, action, *, version, request_id='', decision=None, hold_id='', pool_revision=''):
    with locked_activity(pk) as activity:
        organizer = action == 'decide'
        if organizer:
            if not activity.can_organize(actor):
                raise Http404
        elif not visible_activities(actor).filter(pk=pk).exists():
            raise Http404
        target = target_for(activity)
        if not target:
            raise Http404
        if activity.is_cancelled:
            return 'Cancelled. Registration and admission history are retained; changes are closed.'
        if str(version) != str(target.version):
            return 'Reload the current registration terms before continuing.'
        from .reservations import maintain_locked, pool_for, withdraw_locked, accept_locked
        maintain_locked(activity, target)
        if action == 'submit':
            latest = current_request(target, actor)
            if latest and latest.closed_at is None:
                return 'Your existing registration request is retained; submission alone secures no place.'
            if str(request_id) != str(latest.pk if latest else ''):
                return 'Reload your current registration request before submitting again.'
            if target.admission == 'invitation' and not is_invited(activity, actor):
                return 'An active invitation to this Activity is required. No registration was submitted.'
            RegistrationRequest.objects.create(target=target, user=actor)
            return 'Registration submitted. No place or payment is confirmed.'
        if not str(request_id).isdigit():
            raise Http404
        application = get_object_or_404(target.requests.select_related('target', 'user', 'decision', 'confirmation__place'), pk=request_id)
        if not organizer and application.user_id != actor.pk:
            raise Http404
        if application.closed_at:
            return 'This request is already closed; its history is retained.'
        if action == 'withdraw':
            withdraw_locked(activity, application)
            now = timezone.now()
            application.closed_at = application.withdrawn_at = now
            application.save(update_fields=['closed_at', 'withdrawn_at'])
            confirmation = getattr(application, 'confirmation', None)
            if confirmation:
                confirmation.ended_at = now
                confirmation.save(update_fields=['ended_at'])
                place = getattr(confirmation, 'place', None)
                if place:
                    place.released_at = now
                    place.save(update_fields=['released_at'])
            maintain_locked(activity, target)
            return 'Registration withdrawn. Any free place is released; history is retained.'
        if action == 'decide':
            if target.admission != 'request' or decision not in {'approved', 'denied'}:
                raise Http404
            if hasattr(application, 'decision'):
                return 'This request already has a decision; history is retained.'
            if decision == 'approved':
                if not application.user.is_active or not visible_activities(application.user).filter(pk=pk).exists():
                    return 'This person cannot currently access the Activity. Nothing changed.'
                if target.allocation == 'approval' and full(target):
                    return 'Full. Request remains pending; no approval or place was promised.'
            RegistrationAdmission.objects.create(request=application, actor=actor, result=decision)
            if decision == 'denied':
                application.closed_at = timezone.now()
                application.save(update_fields=['closed_at'])
                return 'Request denied; no place allocated. History is retained.'
            if target.allocation == 'approval':
                secure_free(application)
                return 'Approved and registered. A free place is secured.'
            return 'Approved — eligible only. No place or payment is confirmed.'
        if action == 'claim':
            if registrations_for(activity).filter(request=application).exists():
                return 'Your free registration is already secured.'
            if not eligible(application, activity):
                return 'Admission is not currently satisfied. No place secured.'
            if target.amount != 0:
                return 'Payment required. Payments are unavailable; no place or paid registration can be confirmed.'
            if pool_for(target):
                return accept_locked(activity, application, hold_id, pool_revision)
            if target.allocation != 'claim':
                return 'Organizer approval must secure this place.'
            if full(target):
                return 'Full. You remain eligible; no place secured and no waitlist created.'
            secure_free(application)
            return 'Registered. Your free place is secured.'
        raise Http404


def facts(application, activity):
    target = application.target
    decision = getattr(application, 'decision', None)
    confirmation = getattr(application, 'confirmation', None)
    place = getattr(confirmation, 'place', None)
    secured = bool(registrations_for(activity).filter(request=application).exists())
    admission = ('Approved' if decision.result == 'approved' else 'Denied') if decision else 'Pending' if target.admission == 'request' else 'Not required' if target.admission == 'open' else 'Invitation active' if is_invited(activity, application.user) else 'Invitation required'
    place_label = 'Released' if place and place.released_at else 'Secured' if place else 'Unlimited' if secured else 'None'
    if application.withdrawn_at:
        state = 'Withdrawn'
    elif decision and decision.result == 'denied':
        state = 'Request denied'
    elif secured:
        state = 'Registered'
    elif eligible(application, activity):
        state = 'Eligible — payment required' if target.amount else 'Eligible — place not secured'
    else:
        state = 'Request sent' if target.admission == 'request' else 'Invitation required'
    return dict(application=application, admission=admission, place=place_label, state=state,
        payment='Required — unavailable' if target.amount else 'Not required', secured=secured,
        can_claim=not activity.is_cancelled and not secured and eligible(application, activity) and target.amount == 0 and target.allocation == 'claim' and not full(target))


def registration_context(request, activity, *, organizer=False):
    target = target_for(activity)
    if not target:
        return {}
    own = current_request(target, request.user)
    own_facts = facts(own, activity) if own else None
    rows = target.requests.select_related('target', 'user__profile', 'decision__actor__profile', 'confirmation__place')
    if not organizer:
        rows = rows.filter(user=request.user)
    from .reservations import reservation_context
    reservation = reservation_context(request, activity, target, own, organizer=organizer)
    if reservation.get('reservation_state') and own_facts and not own_facts['secured'] and not own.closed_at:
        own_facts['state'] = reservation['reservation_state']
    if reservation:
        if own_facts:
            own_facts['can_claim'] = False
    return dict(**reservation, registration_capacity=reservation['reservation_pool'].capacity if reservation else target.capacity, registration_target=target, registration_request=own, registration_facts=own_facts,
        registration_state=own_facts['state'] if own else '', registration_rows=[facts(row, activity) for row in rows],
        registration_count=registrations_for(activity).count(), registration_full=full(target),
        registration_can_submit=target.admission != 'invitation' or is_invited(activity, request.user))


@login_required
@require_POST
def registration_action(request, pk, action):
    if action not in {'submit', 'claim', 'withdraw'}:
        raise Http404
    notice = mutate(pk, request.user, action, version=request.POST.get('policy', ''), request_id=request.POST.get('request', ''), hold_id=request.POST.get('hold', ''), pool_revision=request.POST.get('pool_revision', ''))
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    from .views import _render_join_region, _participation_next_path
    if request.headers.get('HX-Request') != 'true':
        messages.info(request, notice)
        return redirect(_participation_next_path(request, activity))
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def decide_registration(request, pk, request_pk):
    notice = mutate(pk, request.user, 'decide', version=request.POST.get('policy', ''), request_id=request_pk, decision=request.POST.get('decision'))
    messages.info(request, notice)
    return redirect(reverse('activities:roster', args=[pk]))
