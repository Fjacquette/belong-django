"""D3: free temporary holds and protected FIFO offers; never payment or attendance.

All writers lock the owning Activity first, then touch registrations/holds/queue.
Expiry is reclaimed before allocation, so correctness requires no worker. GETs
only derive deadline state; the optional sweeper or any valid POST records cleanup.
"""
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (FreeReservationPool, FreeReservationHold, FreeWaitlistEntry,
                     FreePoolCapacityChange, RegistrationRequest, RegistrationPlace)
from .participation import locked_activity
from .registration import eligible, registrations_for, secure_free, occupied
from .visibility import visible_activities

HOLD_DURATION = timedelta(minutes=10)
OFFER_DURATION = timedelta(hours=24)


def pool_for(target):
    return getattr(target, 'reservation_pool', None) if target else None


def live_holds(pool, now=None):
    return pool.holds.filter(ended_at__isnull=True, expires_at__gt=now or timezone.now())


def used(pool, now=None):
    return occupied(pool.target) + live_holds(pool, now).count()


def end_entry(entry, reason, now):
    if entry and entry.ended_at is None:
        entry.ended_at = now
        entry.end_reason = reason
        entry.save(update_fields=['ended_at', 'end_reason'])


def end_hold(hold, reason, now):
    if hold.ended_at is None:
        hold.ended_at = now
        hold.end_reason = reason
        hold.save(update_fields=['ended_at', 'end_reason'])
        if hold.entry_id:
            end_entry(hold.entry, reason, now)


def maintain_locked(activity, target, *, now=None):
    """Idempotent cleanup and promotion. Caller owns the authoritative Activity lock."""
    pool = pool_for(target)
    if not pool:
        return
    now = now or timezone.now()
    if activity.is_cancelled:
        cancel_locked(pool, now)
        return
    for hold in pool.holds.filter(ended_at__isnull=True).select_related('entry', 'request__target', 'request__user'):
        reason = 'expired' if hold.expires_at <= now else 'ineligible' if not eligible(hold.request, activity) else ''
        if reason:
            end_hold(hold, reason, now)
    # Pending entries must remain admission-eligible. Loss is recorded, never
    # silently turned into confirmed intent or allowed to block the whole queue.
    for entry in pool.entries.filter(ended_at__isnull=True, offer__isnull=True).select_related('request__target', 'request__user'):
        if not eligible(entry.request, activity):
            end_entry(entry, 'ineligible', now)
    if not pool.waitlist_enabled:
        return
    available = pool.capacity - used(pool, now)
    for entry in pool.entries.filter(ended_at__isnull=True, offer__isnull=True).select_related('request__target', 'request__user').order_by('pk')[:max(available, 0)]:
        hold = FreeReservationHold.objects.create(pool=pool, request=entry.request, user_id=entry.user_id, entry=entry, expires_at=now + OFFER_DURATION)
        # One event per offer, durable even when delivery is unavailable/opted out.
        from .notifications import queue_event
        queue_event(activity, activity.host, 'place_offer', reservation_hold=hold)


def cancel_locked(pool, now):
    for hold in pool.holds.filter(ended_at__isnull=True).select_related('entry'):
        end_hold(hold, 'cancelled', now)
    for entry in pool.entries.filter(ended_at__isnull=True):
        end_entry(entry, 'cancelled', now)


def withdraw_locked(activity, application):
    pool = pool_for(application.target)
    if pool:
        now = timezone.now()
        for hold in pool.holds.filter(request=application, ended_at__isnull=True).select_related('entry'):
            end_hold(hold, 'withdrawn', now)
        for entry in pool.entries.filter(request=application, ended_at__isnull=True):
            end_entry(entry, 'withdrawn', now)


def accept_locked(activity, application, hold_id, revision):
    pool = pool_for(application.target)
    if str(revision) != str(pool.revision):
        return 'Reload the current capacity policy before confirming.'
    if not str(hold_id).isdigit():
        return 'Reserve a free place or review your waitlist offer before confirming.'
    hold = get_object_or_404(pool.holds.select_related('entry'), pk=hold_id, request=application, user=application.user)
    if hold.ended_at:
        if hold.end_reason == 'accepted' and registrations_for(activity).filter(request=application).exists():
            return 'Your free registration is already secured.'
        return 'This hold or offer has ended. No new place was confirmed.'
    now = timezone.now()
    if hold.expires_at <= now:
        end_hold(hold, 'expired', now)
        maintain_locked(activity, application.target, now=now)
        return 'Expired. No place confirmed; request a new hold or explicitly rejoin the waitlist.'
    if not eligible(application, activity):
        return 'Admission is not currently satisfied. No place confirmed.'
    if registrations_for(activity).filter(request=application).exists():
        return 'Your free registration is already secured.'
    # Replace our own counted live hold with one secured place atomically.
    if used(pool, now) > pool.capacity:
        return 'Capacity needs organizer review. Nothing changed.'
    end_hold(hold, 'accepted', now)
    secure_free(application)
    return 'Registered. Your free place is secured; attendance remains separate.'


def mutate(pk, user, action, *, policy, revision, request_id='', hold_id='', entry_id=''):
    with locked_activity(pk) as activity:
        if not visible_activities(user).filter(pk=pk).exists():
            raise Http404
        target = getattr(activity, 'registration_target', None) if activity.is_registration else None
        pool = pool_for(target)
        if not pool:
            raise Http404
        if activity.is_cancelled:
            return 'Cancelled. Holds and queue history are retained; participation is closed.'
        if str(policy) != str(target.version) or str(revision) != str(pool.revision):
            return 'Reload the current reservation policy before continuing.'
        if not str(request_id).isdigit():
            raise Http404
        application = get_object_or_404(target.requests.select_related('target', 'user'), pk=request_id, user=user)
        maintain_locked(activity, target)
        if application.closed_at:
            return 'This registration request is closed. History is retained.'
        if action == 'refresh':
            return 'Availability checked. Deadlines are unchanged.'
        if action == 'accept':
            return accept_locked(activity, application, hold_id, revision)
        if action == 'release':
            if not str(hold_id).isdigit():
                raise Http404
            hold = get_object_or_404(pool.holds.select_related('entry'), pk=hold_id, request=application, user=user)
            if hold.ended_at:
                return 'This hold or offer is already ended. Registration is unchanged; withdraw registration to release a secured place.'
            end_hold(hold, 'declined' if hold.entry_id else 'withdrawn', timezone.now())
            maintain_locked(activity, target)
            return 'Hold or offer released. History is retained.'
        if action == 'leave_queue':
            if not str(entry_id).isdigit():
                raise Http404
            entry = get_object_or_404(pool.entries, pk=entry_id, request=application, user=user)
            if entry.ended_at:
                return 'This waitlist entry has ended. Registration and history are unchanged.'
            if hasattr(entry, 'offer'):
                end_hold(entry.offer, 'withdrawn', timezone.now())
            end_entry(entry, 'withdrawn', timezone.now())
            maintain_locked(activity, target)
            return 'Left the waitlist. Registration request and history are retained.'
        if not eligible(application, activity):
            return 'Admission is not currently satisfied. No hold or waitlist entry created.'
        if registrations_for(activity).filter(request=application).exists():
            return 'You are already registered; no hold or queue entry is needed.'
        existing = live_holds(pool).filter(user=user).first()
        if existing:
            return 'Your existing hold or offer is retained with the same deadline.'
        if action == 'hold':
            if pool.entries.filter(user=user, ended_at__isnull=True).exists():
                return 'Your waitlist priority is retained. Check availability for an offer.'
            latest = pool.holds.filter(user=user).last()
            if str(hold_id) != str(latest.pk if latest else ''):
                return 'Reload the ended hold before reserving again.'
            if used(pool) >= pool.capacity:
                return 'Full. No hold, registration or waitlist entry was created.'
            FreeReservationHold.objects.create(pool=pool, request=application, user=user, expires_at=timezone.now() + HOLD_DURATION)
            return 'Place held for 10 minutes. Confirm explicitly before its deadline; you are not registered yet.'
        if action == 'join_queue':
            if not pool.waitlist_enabled:
                raise Http404
            existing = pool.entries.filter(user=user, ended_at__isnull=True).first()
            if existing:
                return 'Your existing waitlist priority is retained.'
            latest = pool.entries.filter(user=user).last()
            if str(entry_id) != str(latest.pk if latest else ''):
                return 'Reload the ended entry before explicitly rejoining at the tail.'
            if used(pool) < pool.capacity:
                return 'A place is available. Reserve it directly; no waitlist entry created.'
            FreeWaitlistEntry.objects.create(pool=pool, request=application, user=user)
            return 'Waitlist joined explicitly. No place or attendance is confirmed.'
        raise Http404


def resize(pk, organizer, capacity, *, policy, revision):
    with locked_activity(pk) as activity:
        if not activity.can_organize(organizer):
            raise Http404
        target = getattr(activity, 'registration_target', None) if activity.is_registration else None
        pool = pool_for(target)
        if not pool:
            raise Http404
        if activity.is_cancelled:
            return 'Cancelled. Capacity cannot change.'
        if str(policy) != str(target.version) or str(revision) != str(pool.revision):
            return 'Reload the current capacity policy before changing it.'
        if not str(capacity).isdigit() or not 1 <= int(capacity) <= 2147483647:
            return 'Choose a positive place limit.'
        maintain_locked(activity, target)
        capacity = int(capacity)
        if capacity < used(pool):
            return 'Capacity cannot be reduced below secured places plus live holds and offers.'
        if capacity == pool.capacity:
            return 'Capacity is unchanged.'
        FreePoolCapacityChange.objects.create(pool=pool, actor=organizer, previous=pool.capacity, capacity=capacity, revision=pool.revision + 1)
        FreeReservationPool.objects.filter(pk=pool.pk, revision=pool.revision).update(capacity=capacity, revision=pool.revision + 1)
        pool.refresh_from_db()
        # Clear the target's relation cache so promotion sees the updated limit.
        target._state.fields_cache.pop('reservation_pool', None)
        maintain_locked(activity, target)
        return 'Capacity updated. Secured places and existing deadlines are retained.'


def reservation_context(request, activity, target, own, *, organizer=False):
    pool = pool_for(target)
    if not pool:
        return {}
    now = timezone.now()
    hold = pool.holds.filter(user=request.user).last()
    entry = pool.entries.filter(user=request.user).last()
    current_hold = bool(own and hold and hold.request_id == own.pk)
    live = bool(current_hold and hold.ended_at is None and hold.expires_at > now)
    queued = bool(own and entry and entry.request_id == own.pk and entry.ended_at is None and not hasattr(entry, 'offer'))
    ready = bool(own and eligible(own, activity) and not registrations_for(activity).filter(request=own).exists())
    held_count = live_holds(pool, now).count()
    state = 'Place offered' if live and hold.entry_id else 'Place held' if live else 'Waitlisted' if queued else ('Offer expired' if hold.entry_id else 'Hold expired') if current_hold and (hold.end_reason == 'expired' or hold.ended_at is None and hold.expires_at <= now) else ''
    position = sum(eligible(row.request, activity) for row in pool.entries.filter(ended_at__isnull=True, offer__isnull=True, pk__lte=entry.pk).select_related('request__target', 'request__user')) if queued else None
    rows = pool.holds.select_related('user__profile', 'entry') if organizer else pool.holds.filter(user=request.user)
    entries = pool.entries.select_related('user__profile') if organizer else pool.entries.filter(user=request.user)
    history = [dict(hold=row, state=row.get_end_reason_display() if row.ended_at else 'Expired' if row.expires_at <= now else 'Offered' if row.entry_id else 'Held') for row in rows]
    return dict(reservation_pool=pool, reservation_hold=hold, reservation_entry=entry,
        reservation_live=live, reservation_queued=queued, reservation_state=state, reservation_position=position,
        reservation_history=history, reservation_entries=entries, reservation_held_count=held_count,
        reservation_remaining=max(0, pool.capacity - occupied(target) - held_count),
        reservation_can_hold=ready and not live and not queued and used(pool, now) < pool.capacity,
        reservation_can_queue=ready and pool.waitlist_enabled and not live and not queued and used(pool, now) >= pool.capacity)


@login_required
@require_POST
def reservation_action(request, pk, action):
    if action not in {'hold', 'accept', 'release', 'join_queue', 'leave_queue', 'refresh'}:
        raise Http404
    notice = mutate(pk, request.user, action, policy=request.POST.get('policy', ''), revision=request.POST.get('pool_revision', ''), request_id=request.POST.get('request', ''), hold_id=request.POST.get('hold', ''), entry_id=request.POST.get('entry', ''))
    activity = get_object_or_404(visible_activities(request.user), pk=pk)
    from .views import _render_join_region, _participation_next_path
    if request.headers.get('HX-Request') != 'true':
        messages.info(request, notice)
        return redirect(_participation_next_path(request, activity))
    return _render_join_region(request, activity, notice)


@login_required
@require_POST
def reservation_capacity(request, pk):
    notice = resize(pk, request.user, request.POST.get('capacity', ''), policy=request.POST.get('policy', ''), revision=request.POST.get('pool_revision', ''))
    messages.info(request, notice)
    return redirect(reverse('activities:roster', args=[pk]))
