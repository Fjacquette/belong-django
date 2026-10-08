"""Exercise real SQLite write serialization, not mocked transaction claims."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from django.test import SimpleTestCase


class NotificationConcurrencyTests(SimpleTestCase):
    def test_duplicate_claims_and_cancellations_are_serialized(self):
        with tempfile.TemporaryDirectory() as directory:
            env={**os.environ,'DJANGO_SETTINGS_MODULE':'belong.settings','BELONG_ENV':'test',
                 'DJANGO_DB_PATH':str(Path(directory)/'concurrency.sqlite3')}
            code='''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.core.management import call_command
from django.db import connections
from django.utils import timezone
from belong.test_helpers import create_legacy_user
from social.models import OutboundEmailAttempt
from activities.models import Activity, ActivityResponse, Announcement, ActivityNotificationEvent, ActivityNotificationDelivery
from activities.notifications import queue_event, deliver_one
from activities.participation import locked_activity, cancel_activity
call_command('migrate', verbosity=0)
host=create_legacy_user('host',email='host@example.invalid')
user=create_legacy_user('user',email='user@example.invalid')
for person in [host,user]:
    person.profile.email_verified_at=timezone.now();person.profile.activity_email_enabled=True;person.profile.save()
activity=Activity.objects.create(host=host,title='Race',description='Coordination')
ActivityResponse.objects.create(activity=activity,user=user,status='more')
with patch('activities.notifications.deliver_event'):
    with locked_activity(activity.pk) as fresh:
        announcement=Announcement.objects.create(activity=fresh,author=host,body='Update')
        queue_event(fresh,host,'update',announcement=announcement)
delivery=ActivityNotificationDelivery.objects.get()
barrier=Barrier(2)
calls=[]
def transport(event, attempt, email):
    calls.append(attempt.pk)
    OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='sent')
    return True
def race_send(i):
    barrier.wait(timeout=10)
    try: return deliver_one(delivery.pk)
    finally: connections.close_all()
with patch('activities.notifications.EMAIL_TRANSPORT',side_effect=transport),ThreadPoolExecutor(max_workers=2) as pool:
    assert sum(pool.map(race_send,range(2)))==1
assert len(calls)==1
barrier=Barrier(2)
def race_cancel(i):
    barrier.wait(timeout=10)
    try: return cancel_activity(activity.pk,host,'Storm')
    finally: connections.close_all()
with patch('activities.notifications.deliver_event'),ThreadPoolExecutor(max_workers=2) as pool:
    assert all(pool.map(race_cancel,range(2)))
assert ActivityNotificationEvent.objects.filter(kind='cancellation').count()==1
activity.refresh_from_db();assert activity.is_cancelled
assert ActivityResponse.objects.get().status=='more'
# A cancellation committed before a queued update claim suppresses that update.
other=Activity.objects.create(host=host,title='Other',description='Race')
ActivityResponse.objects.create(activity=other,user=user,status='committed')
with patch('activities.notifications.deliver_event'):
    with locked_activity(other.pk) as fresh:
        announcement=Announcement.objects.create(activity=fresh,author=host,body='Update')
        event=queue_event(fresh,host,'update',announcement=announcement)
    cancel_activity(other.pk,host,'Storm')
assert not deliver_one(event.deliveries.get().pk)
assert event.deliveries.get().reason=='superseded_by_cancellation'
# Participation racing cancellation is either captured before the cancellation
# or refused after it. The email audience must match that serialized result.
from activities.participation import change_response
race_activity=Activity.objects.create(host=host,title='Participation race',description='Race')
barrier=Barrier(2)
def race_participation(i):
    barrier.wait(timeout=10)
    try:
        if i==0: return cancel_activity(race_activity.pk,host,'Storm')
        return change_response(race_activity.pk,user,'more')
    finally: connections.close_all()
with patch('activities.notifications.deliver_event'),ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(race_participation,range(2)))
race_activity.refresh_from_db()
race_event=ActivityNotificationEvent.objects.get(activity=race_activity,kind='cancellation')
assert race_event.deliveries.count()==race_activity.responses.count()
assert all(r.updated_at <= race_activity.cancelled_at for r in race_activity.responses.all())
'''
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
