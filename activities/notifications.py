"""Durable occurrence notifications. SMTP always runs after the source transaction.

Email is deliberately a fixed notice, not a relay for organizer-authored text.
Recipient snapshots can shrink at dispatch, never expand or follow a changed address.
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone

from belong.email_controls import address_hash, dispatch, lock_controls, owned_url
from social.models import OutboundEmailAttempt
from .models import ActivityNotificationDelivery, ActivityNotificationEvent
from .polls import recipient_ids, has_response
from django.contrib.auth import get_user_model
from .visibility import visible_activities


def eligibility(event, user, *, expected_hash=None):
    if user is None or not user.is_active:
        return 'recipient_inactive'
    profile = user.profile
    if not profile.email_verified_at:
        return 'recipient_unverified'
    if not profile.activity_email_enabled:
        return 'recipient_opted_out'
    try:
        validate_email(user.email)
    except ValidationError:
        return 'recipient_no_email'
    if expected_hash and address_hash(user.email) != expected_hash:
        return 'recipient_address_changed'
    if not visible_activities(user).filter(pk=event.activity_id).exists():
        return 'recipient_no_access'
    if event.kind == 'confirmation':
        if event.activity.is_cancelled:
            return 'superseded_by_cancellation'
        if not event.confirmation_round or not event.confirmation_round.invitations.filter(user=user).exists():
            return 'recipient_no_invitation'
        if has_response(event.activity,user):
            return 'confirmation_already_answered'
    elif user.pk not in recipient_ids(event.activity):
        return 'recipient_no_response'
    return ''


def sender_reason(event):
    actor = event.actor
    if not actor.is_active or not actor.profile.email_verified_at:
        return 'sender_unverified'
    if actor.profile.outbound_mail_suspended:
        return 'sender_suspended'
    if not event.activity.can_organize(actor):
        return 'sender_not_organizer'
    return ''


def queue_event(activity, actor, kind, *, announcement=None, confirmation_round=None):
    """Caller holds the occurrence lock. Snapshot consent and addresses at event time."""
    event, created = ActivityNotificationEvent.objects.get_or_create(
        **({'confirmation_round':confirmation_round} if confirmation_round else {'announcement': announcement} if announcement else {'activity': activity, 'kind': kind}),
        defaults={'activity': activity, 'actor': actor, 'kind': kind})
    if not created:
        return event
    ids = set(confirmation_round.invitations.values_list('user_id',flat=True)) if confirmation_round else recipient_ids(activity)
    recipients = get_user_model().objects.filter(pk__in=ids).select_related('profile')
    if kind != 'confirmation':
        recipients = recipients.exclude(pk=actor.pk)
    reason = sender_reason(event)
    for user in recipients:
        blocked = reason or eligibility(event, user)
        ActivityNotificationDelivery.objects.create(event=event, recipient=user, recipient_hash=address_hash(user.email),
            status='skipped' if blocked else 'pending', reason=blocked)
    transaction.on_commit(lambda: deliver_event(event.pk), robust=True)
    return event


def _quota_reason(event, delivery, now):
    limits = settings.ACTIVITY_NOTIFICATION_LIMITS
    recent = OutboundEmailAttempt.objects.exclude(outcome='blocked').filter(created_at__gt=now-timedelta(days=1))
    kind = 'activity_cancellation' if event.kind == 'cancellation' else 'activity_update'
    # Updates share the existing invitation actor budget; cancellation has a
    # separate reserved budget so routine messages cannot consume its urgency.
    kinds = [kind] if event.kind == 'cancellation' else [kind, 'invitation']
    cap = limits['cancellation_actor_day'] if event.kind == 'cancellation' else settings.EMAIL_LIMITS['invitation_attempts_day']
    if recent.filter(actor=event.actor, kind__in=kinds).count() >= cap:
        return 'actor_day'
    if recent.filter(kind=kind, recipient_hash=delivery.recipient_hash,
                     created_at__gt=now-timedelta(hours=1)).count() >= limits['recipient_hour']:
        return 'recipient_hour'
    return ''


def deliver_one(pk):
    """Claim atomically, then send without a write lock. A claimed row is never reclaimed.

    Interrupted SMTP has an unknowable outcome; stale claims become 'unknown',
    requiring provider reconciliation rather than a blind duplicate send.
    """
    with transaction.atomic():
        lock_controls()
        delivery = ActivityNotificationDelivery.objects.select_for_update().select_related(
            'event__activity__group', 'event__actor__profile', 'recipient__profile').get(pk=pk)
        now = timezone.now()
        if delivery.status not in {'pending', 'failed'} or delivery.retry_at > now or delivery.attempts >= settings.ACTIVITY_NOTIFICATION_LIMITS['max_attempts']:
            return False
        event = delivery.event
        reason = sender_reason(event) or eligibility(event, delivery.recipient, expected_hash=delivery.recipient_hash)
        if event.kind == 'update' and event.activity.cancelled_at and event.created_at < event.activity.cancelled_at:
            reason = 'superseded_by_cancellation'
        if event.created_at < now-timedelta(days=7):
            reason = 'expired'
        if reason:
            delivery.status = 'skipped'; delivery.reason = reason
            delivery.save(update_fields=['status', 'reason', 'updated_at'])
            return False
        quota = _quota_reason(event, delivery, now)
        attempt = OutboundEmailAttempt.objects.create(kind='activity_cancellation' if event.kind == 'cancellation' else 'activity_update',
            actor=event.actor, recipient_hash=delivery.recipient_hash, ip_hash='', activity_reference=event.activity_id,
            outcome='blocked' if quota else 'reserved', reason=quota)
        delivery.attempt = attempt
        if quota:
            delivery.reason = quota
            delivery.retry_at = now+timedelta(hours=1)
            delivery.save(update_fields=['reason', 'retry_at', 'attempt', 'updated_at'])
            return False
        delivery.status = 'sending'; delivery.reason = ''; delivery.attempts += 1
        delivery.save(update_fields=['status', 'reason', 'attempts', 'attempt', 'updated_at'])
        email = delivery.recipient.email
    try:
        result = EMAIL_TRANSPORT(event, attempt, email)
    except Exception as error:
        # Configuration/transport errors remain auditable without exposing payloads.
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='failed', reason=('transport_'+type(error).__name__)[:80])
        result = False
    attempt.refresh_from_db()
    ambiguous = attempt.reason in {'delivery_SMTPServerDisconnected', 'delivery_TimeoutError', 'delivery_ConnectionResetError'}
    ActivityNotificationDelivery.objects.filter(pk=pk, status='sending').update(
        status='sent' if result else ('unknown' if ambiguous else 'failed'), reason='' if result else (attempt.reason or 'delivery_failed'),
        retry_at=timezone.now()+timedelta(seconds=settings.ACTIVITY_NOTIFICATION_LIMITS['retry_seconds']), updated_at=timezone.now())
    return result


def email_transport(event, attempt, email):
    link = owned_url('activities:detail', event.activity_id)
    preferences = owned_url('account_settings')
    if event.kind == 'confirmation':
        subject = 'Please confirm attendance — Belong'
        text = 'A date poll you answered has been finalized. Please check the selected date and confirm or decline attendance. Your poll answers have not reserved a place.'
    elif event.kind == 'cancellation':
        subject = 'Activity cancelled — Belong'
        text = 'An Activity you responded to has been cancelled. Please check Details before travelling.'
    else:
        subject = 'Activity update — Belong'
        text = 'The organizer posted an update to an Activity you responded to. Please check Details for the latest information.'
    if event.activity.is_free_ongoing:
        text = ('An ongoing opportunity you enrolled in has been cancelled. Check Details for retained enrollment history. Separate meetings are unchanged.'
                if event.kind == 'cancellation' else 'The organizer posted an update to an ongoing opportunity you enrolled in. Check Details for the latest information.')
    if event.activity.is_registration:
        text = ('An Activity you registered for has been cancelled. Check Details for retained free registration history.' if event.kind == 'cancellation' else 'The organizer posted an update to an Activity you registered for. Check Details for the latest information.')
    ending = 'This confirmation invitation does not subscribe you to routine updates.' if event.kind == 'confirmation' else 'Declining or removing your response stops future notices for this Activity.'
    if event.activity.is_free_ongoing:
        ending = 'Leaving ongoing enrollment stops future notices for this opportunity.'
    if event.activity.is_registration:
        ending = 'Withdrawing registration stops future notices for this Activity.'
    return dispatch(attempt, subject, f'{text}\n\nDetails (sign-in required): {link}\n\n'
                    f'You opted in to Activity emails. Change your preference: {preferences}\n' + ending, email)


# Only one transport is implemented; events and audience logic are transport independent.
EMAIL_TRANSPORT = email_transport


def deliver_event(event_id):
    for pk in ActivityNotificationDelivery.objects.filter(event_id=event_id, status='pending').order_by('pk').values_list('pk', flat=True)[:settings.EMAIL_LIMITS['invitation_batch']]:
        deliver_one(pk)


def drain_notifications(limit=100):
    now = timezone.now()
    ActivityNotificationDelivery.objects.filter(status='sending', updated_at__lt=now-timedelta(minutes=15)).update(
        status='unknown', reason='interrupted_delivery', updated_at=now)
    ids = list(ActivityNotificationDelivery.objects.filter(status__in=['pending', 'failed'], retry_at__lte=now,
        attempts__lt=settings.ACTIVITY_NOTIFICATION_LIMITS['max_attempts']).annotate(priority=Case(When(event__kind='cancellation', then=Value(0)), default=Value(1), output_field=IntegerField())).order_by('priority', 'event__created_at', 'pk').values_list('pk', flat=True)[:limit])
    return sum(deliver_one(pk) for pk in ids)
