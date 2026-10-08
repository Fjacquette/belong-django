import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .models import Activity, ActivityResponse, ActivitySeries


class OccurrenceLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('hike-host')
        cls.viewer = create_legacy_user('hike-viewer')
        cls.other = create_legacy_user('hike-other')
        cls.coorganizer = create_legacy_user('hike-coorganizer')
        cls.group = Group.objects.create(owner=cls.host, name='Hikers')
        GroupMembership.objects.create(group=cls.group, user=cls.viewer)
        GroupMembership.objects.create(group=cls.group, user=cls.coorganizer, role='organizer')
        cls.series = ActivitySeries.objects.create(owner=cls.host, group=cls.group, title='Weekend hikes', description='Walk together')
        cls.activity = Activity.objects.create(host=cls.host, group=cls.group, series=cls.series, title='Saturday hike',
                                              description='Meet at the trail', available_responses=['committed', 'question'], capacity=1)
        cls.sibling = Activity.objects.create(host=cls.host, group=cls.group, series=cls.series, title='Next hike', description='Next week')

    def setUp(self):
        self.client.force_login(self.host)

    def post(self, route, user=None, **data):
        if user:
            self.client.force_login(user)
        return self.client.post(reverse('activities:'+route, args=[self.activity.pk]), data)

    def test_roster_is_private_to_host_and_active_group_organizers(self):
        for user in [self.host, self.coorganizer]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('activities:roster', args=[self.activity.pk])).status_code, 200)
        for user in [self.viewer, self.other]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('activities:roster', args=[self.activity.pk])).status_code, 404)
            self.assertEqual(self.post('cancel', reason='Unauthorized').status_code, 404)
        member = GroupMembership.objects.get(group=self.group, user=self.coorganizer)
        member.role = 'member'; member.status = 'blocked'; member.save()
        self.client.force_login(self.coorganizer)
        self.assertEqual(self.post('cancel').status_code, 404)
        self.activity.refresh_from_db()
        self.assertFalse(self.activity.is_cancelled)

    def test_ungrouped_activity_host_is_the_only_organizer(self):
        self.activity.group = None; self.activity.series = None; self.activity.save()
        self.client.force_login(self.coorganizer)
        self.assertEqual(self.client.get(reverse('activities:roster', args=[self.activity.pk])).status_code, 404)
        self.assertEqual(self.post('cancel').status_code, 404)
        self.client.force_login(self.host)
        self.assertEqual(self.post('cancel').status_code, 302)

    def test_roster_uses_selected_vocabulary_and_preserves_historical_choices(self):
        self.viewer.profile.display_name = 'Trail Walker'; self.viewer.profile.save()
        ActivityResponse.objects.create(activity=self.activity, user=self.viewer, status='question')
        ActivityResponse.objects.create(activity=self.activity, user=self.other, status='declined')
        page = self.client.get(reverse('activities:roster', args=[self.activity.pk]))
        self.assertContains(page, 'Trail Walker')
        self.assertContains(page, 'I have a question: 1')
        self.assertContains(page, 'Count me in: 0')
        self.assertContains(page, 'Cannot make it: 1')
        self.assertNotContains(page, 'Interested:')
        self.assertNotContains(page, 'aria-label="Create"')

    def test_cancel_preserves_responses_group_series_sibling_and_first_reason(self):
        ActivityResponse.objects.create(activity=self.activity, user=self.viewer, status='committed', note='Existing note')
        before = list(ActivityResponse.objects.values())
        group = Group.objects.values().get(pk=self.group.pk)
        series = ActivitySeries.objects.values().get(pk=self.series.pk)
        sibling = Activity.objects.values().get(pk=self.sibling.pk)
        self.assertRedirects(self.post('cancel', self.coorganizer, reason='Trail closed'), reverse('activities:roster', args=[self.activity.pk]))
        self.activity.refresh_from_db()
        first_time = self.activity.cancelled_at
        self.assertTrue(self.activity.is_cancelled)
        self.assertEqual(self.activity.cancelled_by, self.coorganizer)
        self.assertEqual(self.activity.cancellation_reason, 'Trail closed')
        self.post('cancel', self.host, reason='Replacement')
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.cancelled_at, first_time)
        self.assertEqual(self.activity.cancellation_reason, 'Trail closed')
        self.assertEqual(list(ActivityResponse.objects.values()), before)
        self.assertEqual(Group.objects.values().get(pk=self.group.pk), group)
        self.assertEqual(ActivitySeries.objects.values().get(pk=self.series.pk), series)
        self.assertEqual(Activity.objects.values().get(pk=self.sibling.pk), sibling)

    def test_cancel_requires_post_and_csrf_and_validates_reason_without_cancelling(self):
        self.assertEqual(self.client.get(reverse('activities:cancel', args=[self.activity.pk])).status_code, 405)
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.host)
        self.assertEqual(secure.post(reverse('activities:cancel', args=[self.activity.pk])).status_code, 403)
        self.assertContains(self.post('cancel', reason='x'*501), 'Ensure this value has at most 500 characters')
        self.activity.refresh_from_db(); self.assertFalse(self.activity.is_cancelled)
        self.assertEqual(self.post('cancel', reason='').status_code, 302)

    def test_cancelled_rendering_and_all_participation_routes_retain_history(self):
        ActivityResponse.objects.create(activity=self.activity, user=self.viewer, status='committed')
        self.post('cancel', reason='<script>Trail closed</script>')
        self.client.force_login(self.viewer)
        before = list(ActivityResponse.objects.values())
        detail = self.client.get(reverse('activities:detail', args=[self.activity.pk]))
        self.assertContains(detail, 'Cancelled')
        self.assertContains(detail, '&lt;script&gt;Trail closed&lt;/script&gt;')
        self.assertNotContains(detail, '<script>Trail closed</script>')
        self.assertNotContains(detail, 'name="status"')
        self.assertNotContains(detail, 'Remove response')
        self.assertNotContains(detail, 'Manage responses and occurrence')
        card = self.client.get(reverse('activities:index'), {'q': 'Saturday hike'})
        self.assertContains(card, 'Cancelled: Saturday hike')
        self.assertContains(card, 'Saved response: Count me in')
        self.assertNotContains(card, 'name="status"')
        for route, data in [('respond', {'status': 'question'}), ('join', {}), ('leave', {})]:
            with self.subTest(route=route):
                self.post(route, **data)
                self.assertEqual(list(ActivityResponse.objects.values()), before)
        self.post('respond', self.other, status='committed')
        self.assertEqual(list(ActivityResponse.objects.values()), before)

    def test_only_commitment_uses_capacity_and_full_rejection_preserves_current_response(self):
        ActivityResponse.objects.create(activity=self.activity, user=self.viewer, status='committed')
        ActivityResponse.objects.create(activity=self.activity, user=self.other, status='question')
        self.client.force_login(self.other)
        response = self.client.post(reverse('activities:respond', args=[self.activity.pk]),
                                    {'status': 'committed', 'variant': 'detail'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'This activity is full. Your response has not changed.')
        self.assertEqual(ActivityResponse.objects.get(activity=self.activity, user=self.other).status, 'question')
        self.activity.available_responses = ['committed', 'more', 'question']; self.activity.save()
        self.post('respond', status='more')
        self.assertEqual(ActivityResponse.objects.get(activity=self.activity, user=self.other).status, 'more')
        self.post('respond', self.viewer, status='committed')  # Selected commitment toggles off.
        self.post('respond', self.other, status='committed')
        self.assertEqual(ActivityResponse.objects.filter(activity=self.activity, status='committed').count(), 1)
        self.post('leave')
        self.assertEqual(ActivityResponse.objects.filter(activity=self.activity, status='committed').count(), 0)

    def test_legacy_join_endpoint_obeys_capacity_and_remains_idempotent(self):
        self.post('join', self.viewer)
        first = ActivityResponse.objects.get(activity=self.activity, user=self.viewer)
        self.post('join')
        self.assertEqual(ActivityResponse.objects.get(activity=self.activity, user=self.viewer).pk, first.pk)
        self.post('join', self.other)
        self.assertFalse(ActivityResponse.objects.filter(activity=self.activity, user=self.other).exists())

    def test_full_non_htmx_fallback_preserves_filtered_discover(self):
        self.post('join', self.viewer)
        destination = '/?q=hike&when=weekend&cost=free&cost=1_10'
        response = self.post('respond', self.other, status='committed', variant='card', next=destination)
        self.assertEqual(response['Location'], destination)
        self.assertFalse(ActivityResponse.objects.filter(activity=self.activity, user=self.other).exists())

    def test_organizer_can_reach_private_audience_occurrence_from_series(self):
        self.activity.audience = 'friends'; self.activity.save()
        self.client.force_login(self.coorganizer)
        page = self.client.get(reverse('activities:series_detail', args=[self.series.pk]))
        self.assertContains(page, reverse('activities:roster', args=[self.activity.pk]))
        self.assertEqual(self.client.get(reverse('activities:detail', args=[self.activity.pk])).status_code, 404)
        roster = self.client.get(reverse('activities:roster', args=[self.activity.pk]))
        self.assertEqual(roster.status_code, 200)
        self.assertNotContains(roster, 'Activity details')

    def test_existing_over_capacity_responses_are_retained_without_accepting_more(self):
        ActivityResponse.objects.create(activity=self.activity, user=self.viewer, status='committed')
        ActivityResponse.objects.create(activity=self.activity, user=self.other, status='committed')
        self.post('respond', self.host, status='committed')
        self.assertEqual(ActivityResponse.objects.filter(activity=self.activity, status='committed').count(), 2)
        self.assertFalse(ActivityResponse.objects.filter(activity=self.activity, user=self.host).exists())

    def test_full_controls_are_disabled_only_for_people_without_commitment(self):
        self.post('join', self.viewer)
        self.client.force_login(self.other)
        detail = self.client.get(reverse('activities:detail', args=[self.activity.pk]))
        options = detail.context['join_context']['response_options']
        self.assertTrue(next(option['disabled'] for option in options if option['value'] == 'committed'))
        self.assertFalse(next(option['disabled'] for option in options if option['value'] == 'question'))
        self.assertContains(detail, 'Count me in · Full')
        self.client.force_login(self.viewer)
        detail = self.client.get(reverse('activities:detail', args=[self.activity.pk]))
        self.assertFalse(next(option['disabled'] for option in detail.context['join_context']['response_options'] if option['value'] == 'committed'))


class CapacityConcurrencyTests(SimpleTestCase):
    def test_file_backed_concurrent_http_commitments_and_cancellation(self):
        with tempfile.TemporaryDirectory() as root:
            env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'belong.settings', 'BELONG_ENV': 'test',
                   'DJANGO_DB_PATH': str(Path(root)/'concurrency.sqlite3'), 'DJANGO_ALLOWED_HOSTS': 'testserver'}
            code = '''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from activities.models import Activity, ActivityResponse, ActivityInvitation
call_command('migrate', verbosity=0)
users = [get_user_model().objects.create_user(f'person-{i}') for i in range(5)]
clients = []
for user in users:
    user.profile.email_verified_at = timezone.now(); user.profile.save()
    client = Client(); client.force_login(user); clients.append(client)
for iteration in range(3):
    activity = Activity.objects.create(host=users[0], title='Race', description='Together', capacity=1, available_responses=['question'])
    for invitee in users[1:]:
        ActivityInvitation.objects.create(activity=activity, user=invitee, invited_by=users[0])
    barrier = Barrier(4)
    def commit(i):
        barrier.wait(timeout=10)
        try:
            route = 'respond' if i % 2 else 'join'
            response = clients[i].post(reverse('activities:'+route, args=[activity.pk]), {'status':'committed'})
            assert response.status_code == 200, response.status_code
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(commit, range(1,5)))
    assert ActivityResponse.objects.filter(activity=activity, status='committed').count() == 1
# Race a cancellation against a commitment. The final record can precede
# cancellation, but never be inserted/changed after the cancellation timestamp.
activity = Activity.objects.create(host=users[0], title='Cancel race', description='Together', capacity=1, available_responses=['question'])
ActivityInvitation.objects.create(activity=activity,user=users[1],invited_by=users[0])
barrier = Barrier(2)
def race(i):
    barrier.wait(timeout=10)
    try:
        route = 'cancel' if i == 0 else 'respond'
        response = clients[i].post(reverse('activities:'+route, args=[activity.pk]), {'status':'committed', 'reason':'Closed'})
        assert response.status_code == (302 if i == 0 else 200)
    finally:
        connections.close_all()
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(race, range(2)))
activity.refresh_from_db()
assert activity.is_cancelled
assert all(r.updated_at <= activity.cancelled_at for r in ActivityResponse.objects.filter(activity=activity))
before = list(ActivityResponse.objects.filter(activity=activity).values())
clients[1].post(reverse('activities:leave', args=[activity.pk]))
assert list(ActivityResponse.objects.filter(activity=activity).values()) == before
'''
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
