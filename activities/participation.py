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


def change_response(pk, user, status=None, *, toggle=False, remove=False):
    with locked_activity(pk) as activity:
        if activity.is_cancelled:
            return 'This activity is cancelled. Responses are retained; participation is closed.'
        if status is None and not remove:
            status = next(iter(activity.active_responses()), None)
        if not remove and status not in activity.active_responses():
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
        return True
