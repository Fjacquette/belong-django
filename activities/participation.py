"""Serialize occurrence participation and cancellation before reading mutable state."""
from contextlib import contextmanager

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Activity, ActivityResponse, ActivityResponseStatus, ActivityStatus


@contextmanager
def locked_activity(pk):
    with transaction.atomic():
        # Write first: SQLite has no SELECT FOR UPDATE; this acquires its writer
        # lock before any reads. On PostgreSQL the UPDATE locks this activity row.
        Activity.objects.filter(pk=pk).update(status=F('status'))
        yield Activity.objects.select_related('group').get(pk=pk)


def change_response(pk, user, status=None, *, action=None, confirmation_round=None, toggle=False, remove=False):
    with locked_activity(pk) as activity:
        if activity.is_free_ongoing:
            return 'Request ongoing enrollment on Details; meeting attendance is separate.'
        if activity.is_date_planning:
            from .polls import change_attendance_locked
            from .visibility import visible_activities
            from django.http import Http404
            if not visible_activities(user).filter(pk=pk).exists():
                raise Http404
            return change_attendance_locked(activity,user,action,confirmation_round,
                toggle=toggle,remove=remove,join=action is None and status is None and not remove)
        if not activity.accepts_responses:
            return 'No response is required for this activity.'
        if activity.is_cancelled:
            return 'This activity is cancelled. Responses are retained; participation is closed.'
        from .invitations import is_invited
        invited = is_invited(activity, user)
        allowed = activity.active_responses() + (['committed', 'declined'] if invited and activity.uses_legacy_participation else [])
        if not activity.uses_legacy_participation and not remove:
            options = activity.participation_options()
            # The old explicit POST /join remains idempotent. Configured /respond
            # requires semantic action IDs, never arbitrary legacy response labels.
            if action is None and status is None:
                action = next(option['value'] for option in options if option['status'] == 'committed')
            selected = next((option for option in options if option['value'] == action), None)
            if not selected:
                return 'Choose an available participation action.'
            status = selected['status']
        if status is None and not remove:
            status = 'committed' if invited else next(iter(activity.active_responses()), None)
        if not remove and status not in allowed:
            return ''
        existing = ActivityResponse.objects.filter(activity=activity, user=user).first()
        if remove or (toggle and existing and existing.status == status):
            if existing:
                existing.delete()
            return ''
        if status == ActivityResponseStatus.COMMITTED and (not existing or existing.status != status):
            committed = ActivityResponse.objects.filter(activity=activity, status=ActivityResponseStatus.COMMITTED).count()
            if activity.capacity is not None and committed >= activity.capacity:
                return 'This activity is full. Your response has not changed.'
        ActivityResponse.objects.update_or_create(activity=activity, user=user, defaults={'status': status})
        from .group_offers import offer_after_response
        offer_after_response(activity, user)
        return ''


def cancel_activity(pk, organizer, reason):
    with locked_activity(pk) as activity:
        if not activity.can_organize(organizer):
            return False
        if not activity.is_cancelled:
            activity.status = ActivityStatus.CANCELLED
            activity.cancellation_reason = reason
            activity.cancelled_at = timezone.now()
            activity.cancelled_by = organizer
            activity.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'cancelled_by', 'updated_at'])
            from .notifications import queue_event
            queue_event(activity, organizer, 'cancellation')
        return True
