"""Slice B exercises semantic intent through the existing capacity authority."""
from copy import deepcopy
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .email_invitations import issue_invitation
from .forms import ActivityForm, ActivitySeriesForm
from .models import Activity, ActivityInvitation, ActivityResponse, ActivitySeries, ActivityNotificationDelivery
from .notifications import queue_event
from .participation import change_response, cancel_activity
from .participation_config import intent_options, make_config, validate_config
from .series import occurrence_initial


class ParticipationPatternTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('pattern-host', email='pattern-host@example.invalid')
        cls.viewer = create_legacy_user('pattern-viewer', email='pattern-viewer@example.invalid')
        cls.other = create_legacy_user('pattern-other', email='pattern-other@example.invalid')
        for user in (cls.host, cls.viewer, cls.other):
            user.profile.email_verified_at = timezone.now()
            user.profile.activity_email_enabled = True
            user.profile.save()

    def setUp(self):
        self.client.force_login(self.viewer)

    def activity(self, pattern='scheduled', **kwargs):
        kwargs.setdefault('participation_config', make_config(pattern, version=2))
        return Activity.objects.create(host=self.host, title='Slice B opportunity', description='Do something together',
            cost_type='free', **kwargs)

    def post(self, activity, action, **kwargs):
        return self.client.post(reverse('activities:respond', args=[activity.pk]),
            {'action': action, 'variant': 'detail', **kwargs}, HTTP_HX_REQUEST='true')

    def test_version_two_actions_are_pattern_specific_and_version_one_stays_navigation_only(self):
        for pattern, actions in [('scheduled', ['confirm_attendance', 'decline_attendance']), ('immediate', ['join_now'])]:
            self.assertEqual([o['value'] for o in intent_options(make_config(pattern, version=2))], actions)
            self.assertEqual(intent_options(make_config(pattern)), [])
            for wrong in ['interested', 'willing', 'question', 'vote', 'pay', 'register', 'answer_poll',
                          'join_now' if pattern == 'scheduled' else 'confirm_attendance']:
                with self.subTest(pattern=pattern, wrong=wrong), self.assertRaises(ValidationError):
                    make_config(pattern, version=2, actions=['view_details', *actions, wrong])
            with self.assertRaises(ValidationError):
                make_config(pattern, version=2, actions=['view_details'])
        for pattern in ['none', 'planning', 'ongoing', 'registration', 'inquiry']:
            with self.assertRaises(ValidationError): make_config(pattern, version=2)
        with self.assertRaises(ValidationError): make_config('scheduled', version=3)

    def test_creator_defaults_remain_legacy_and_new_presets_use_server_owned_actions(self):
        for form_type in [ActivityForm, ActivitySeriesForm]:
            for pattern in ['scheduled', 'immediate']:
                form = form_type({'title': 'Together', 'description': 'A useful activity', 'audience': 'everyone',
                    'location_type': 'tbd', 'cost_type': 'free', 'cadence': 'flexible', 'participation_pattern': pattern,
                    'available_responses': ['question', 'vote'], 'participation_config': '{"version":99}',
                    'action1_url': 'https://example.invalid/game'}, user=self.host)
                self.assertTrue(form.is_valid(), form.errors)
                instance = form.save(commit=False)
                self.assertEqual(instance.participation_config['version'], 2)
                self.assertEqual(instance.participation_config['pattern'], pattern)
                if form_type is ActivityForm:
                    self.assertIn('open_external', instance.participation_config['actions'])
                self.assertEqual(instance.available_responses, [])
            self.assertEqual(form_type(user=self.host).initial['participation_pattern'], '')

    def test_free_open_policy_rejects_paid_unknown_and_nonzero_cost_without_affecting_legacy(self):
        for pattern in ['scheduled', 'immediate']:
            for cost, amount in [('paid', '25'), ('unknown', ''), ('free', '25')]:
                for form_type in [ActivityForm, ActivitySeriesForm]:
                    form = form_type({'title':'Invalid policy', 'description':'Together', 'audience':'everyone',
                        'location_type':'tbd', 'participation_pattern':pattern, 'cost_type':cost, 'cost_amount':amount}, user=self.host)
                    self.assertFalse(form.is_valid())
                    self.assertIn('cost_amount' if cost == 'free' else 'cost_type', form.errors)
                a = Activity(host=self.host, title='Invalid', cost_type=cost, cost_amount=25 if amount else None,
                             participation_config=make_config(pattern, version=2))
                with self.assertRaises(ValidationError): a.save()
        a = self.activity()
        a.cost_type = 'paid'; a.cost_amount = 25
        with self.assertRaises(ValidationError): a.save(update_fields=['cost_type', 'cost_amount'])
        legacy = Activity.objects.create(host=self.host, title='Legacy paid', cost_type='paid', cost_amount=25)
        self.assertIsNone(legacy.participation_config)

    def test_ordinary_and_invited_controls_match_scheduled_or_immediate_pattern(self):
        for pattern, actions, prompt in [('scheduled', ['confirm_attendance','decline_attendance'], 'Confirm attendance below'),
                                          ('immediate', ['join_now'], 'Join now below')]:
            a = self.activity(pattern)
            detail = self.client.get(a.get_absolute_url())
            self.assertEqual([o['value'] for o in detail.context['join_context']['response_options']], actions)
            card = self.client.get('/?q=Slice+B')
            self.assertContains(card, 'See details')
            ordinary = next(item for item in card.context['activities'] if item.pk == a.pk)
            self.assertEqual(ordinary.j_card_response_options, [])
            ActivityInvitation.objects.create(activity=a, user=self.viewer, invited_by=self.host)
            detail = self.client.get(a.get_absolute_url())
            self.assertContains(detail, prompt)
            self.assertEqual([o['value'] for o in detail.context['join_context']['response_options']], actions)
            card = self.client.get('/?q=Slice+B')
            # Scope the assertions to this Activity's join context.
            rendered = next(item for item in card.context['activities'] if item.pk == a.pk)
            self.assertEqual([o['value'] for o in rendered.j_card_response_options], actions)
        self.assertFalse(ActivityResponse.objects.exists())

    def test_scheduled_toggle_decline_removal_counts_roster_and_capacity(self):
        a = self.activity(capacity=1)
        self.assertContains(self.post(a, 'confirm_attendance'), 'You: Going')
        saved = ActivityResponse.objects.get(activity=a, user=self.viewer)
        self.assertEqual(saved.status, 'committed')
        self.assertContains(self.client.get(a.get_absolute_url()), '1 / 1 places secured')
        self.client.force_login(self.other)
        self.assertContains(self.post(a, 'confirm_attendance'), 'full. Your response has not changed')
        self.assertFalse(ActivityResponse.objects.filter(activity=a, user=self.other).exists())
        self.assertContains(self.post(a, 'decline_attendance'), "You: Can&#x27;t make it")
        self.client.force_login(self.host)
        roster = self.client.get(reverse('activities:roster', args=[a.pk]))
        self.assertContains(roster, 'Going: 1'); self.assertContains(roster, "Can&#x27;t make it: 1")
        self.assertNotContains(roster, 'Count me in')
        self.client.force_login(self.viewer)
        self.post(a, 'decline_attendance'); saved.refresh_from_db(); self.assertEqual(saved.status, 'declined')
        self.client.force_login(self.other)
        self.post(a, 'confirm_attendance')
        self.assertEqual(ActivityResponse.objects.get(activity=a, user=self.other).status, 'committed')
        self.assertEqual(ActivityResponse.objects.filter(activity=a, status='committed').count(), 1)
        self.client.post(reverse('activities:leave', args=[a.pk]))
        self.assertFalse(ActivityResponse.objects.filter(activity=a, user=self.other).exists())
        self.client.force_login(self.viewer)
        self.post(a, 'confirm_attendance'); self.post(a, 'confirm_attendance')
        self.assertFalse(ActivityResponse.objects.filter(activity=a, user=self.viewer).exists())

    def test_immediate_join_now_is_intent_and_external_navigation_never_writes(self):
        # A valid link also needs the explicit capability; never turn clicks into intent.
        b = self.activity('immediate', action1_label='Open game', action1_url='https://example.invalid/game',
                          capacity=1, participation_config=make_config('immediate', version=2,
                              actions=['view_details','join_now','open_external']))
        for _ in range(2):
            self.assertContains(self.client.get(b.get_absolute_url()), 'href="https://example.invalid/game"')
            self.client.get('/?q=Slice+B')
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertContains(self.post(b, 'join_now'), 'You: Joining')
        self.assertContains(self.client.get('/?q=Slice+B'), 'Joining / Edit response')
        self.assertNotContains(self.client.get(b.get_absolute_url()), 'You: Going')
        self.client.force_login(self.host)
        self.assertContains(self.client.get(reverse('activities:roster', args=[b.pk])), 'Joining: 1')
        self.client.force_login(self.other)
        self.assertContains(self.post(b, 'join_now'), 'full. Your response has not changed')
        self.client.force_login(self.viewer)
        self.post(b, 'join_now')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_cross_pattern_or_raw_status_forgery_does_not_mutate_current_intent(self):
        for pattern, real in [('scheduled','confirm_attendance'), ('immediate','join_now')]:
            a = self.activity(pattern)
            self.post(a, real)
            before = ActivityResponse.objects.values().get(activity=a, user=self.viewer)
            ActivityInvitation.objects.create(activity=a, user=self.viewer, invited_by=self.host)
            for wrong in ['committed','declined','interested','willing','question','vote','open_external','answer_poll',
                          'join_now' if pattern == 'scheduled' else 'decline_attendance']:
                self.post(a, wrong)
                self.client.post(reverse('activities:respond', args=[a.pk]), {'status':wrong})
                self.assertEqual(ActivityResponse.objects.values().get(activity=a, user=self.viewer), before)

    def test_join_endpoint_is_explicit_post_and_idempotent_for_both_patterns(self):
        for pattern in ['scheduled','immediate']:
            a = self.activity(pattern)
            route = reverse('activities:join', args=[a.pk])
            self.assertEqual(self.client.get(route).status_code, 405)
            self.client.post(route); before = ActivityResponse.objects.values().get(activity=a, user=self.viewer)
            self.client.post(route)
            self.assertEqual(ActivityResponse.objects.values().get(activity=a, user=self.viewer)['status'], 'committed')
            self.assertEqual(ActivityResponse.objects.filter(activity=a).count(), 1)
            self.assertEqual(ActivityResponse.objects.get(activity=a).pk, before['id'])

    def test_htmx_and_non_js_changes_removal_and_toggles_preserve_discover_context(self):
        destination = '/?q=trail&audience=everyone&audience=friends&cost=free'
        for pattern, action in [('scheduled','confirm_attendance'), ('immediate','join_now')]:
            a = self.activity(pattern)
            ActivityInvitation.objects.create(activity=a, user=self.viewer, invited_by=self.host)
            route = reverse('activities:respond', args=[a.pk])
            changed = self.client.post(route, {'action':action,'variant':'card','next':destination}, HTTP_HX_REQUEST='true')
            self.assertContains(changed, 'aria-pressed="true"')
            self.assertContains(changed, 'name="next" value="/?q=trail&amp;audience=everyone&amp;audience=friends&amp;cost=free"')
            for data in [{'action':action}, {'action':action}, {'action':'decline_attendance'}] if pattern == 'scheduled' else [{'action':action}, {'action':action}]:
                fallback = self.client.post(route, {**data, 'variant':'card','next':destination})
                self.assertEqual(fallback.status_code, 302); self.assertEqual(fallback.url, destination)
            removed = self.client.post(reverse('activities:leave', args=[a.pk]), {'variant':'detail','next':destination})
            self.assertEqual(removed.url, destination)
            self.assertFalse(ActivityResponse.objects.filter(activity=a).exists())
            self.assertContains(self.client.get(a.get_absolute_url()+'?discover='+destination.replace('&','%26')), 'Back to activities')

    def test_cancellation_preserves_responses_and_closes_all_semantic_mutations(self):
        for pattern, action in [('scheduled','confirm_attendance'), ('immediate','join_now')]:
            a = self.activity(pattern)
            self.post(a, action)
            before = ActivityResponse.objects.values().get(activity=a)
            self.assertTrue(cancel_activity(a.pk, self.host, 'Weather'))
            for wrong in [action, 'decline_attendance']:
                self.post(a, wrong)
            self.client.post(reverse('activities:leave', args=[a.pk]))
            self.client.post(reverse('activities:join', args=[a.pk]))
            self.assertEqual(ActivityResponse.objects.values().get(activity=a), before)
            card = self.client.get('/?q=Slice+B')
            self.assertContains(card, '>Cancelled</a>')
            self.assertNotContains(card, 'name="action"')
            self.assertContains(self.client.get(a.get_absolute_url()), 'responses are retained')

    def test_invitation_visibility_group_independence_and_removal_keep_saved_intent(self):
        group = Group.objects.create(owner=self.host, name='Optional context', access='private')
        for pattern, action in [('scheduled','confirm_attendance'), ('immediate','join_now')]:
            a = self.activity(pattern, group=group, invite_group_members=True)
            GroupMembership.objects.create(group=group, user=self.viewer)
            self.assertContains(self.client.get(a.get_absolute_url()), 'You’re invited')
            self.post(a, action); before = ActivityResponse.objects.values().get(activity=a)
            GroupMembership.objects.filter(group=group,user=self.viewer).delete()
            ActivityInvitation.objects.create(activity=a, user=self.viewer, invited_by=self.host)
            ActivityInvitation.objects.filter(activity=a).delete()
            self.assertEqual(ActivityResponse.objects.values().get(activity=a), before)
            self.assertNotContains(self.client.get(a.get_absolute_url()), 'You’re invited')
            self.assertFalse(GroupMembership.objects.filter(group=group,user=self.viewer).exists())
            private = self.activity(pattern, audience='friends')
            ActivityInvitation.objects.create(activity=private, user=self.viewer, invited_by=self.host)
            self.assertEqual(self.client.get(private.get_absolute_url()).status_code, 404)
            self.assertEqual(self.post(private, action).status_code, 404)
            self.assertFalse(ActivityResponse.objects.filter(activity=private).exists())

    def test_version_one_and_legacy_history_are_never_reinterpreted_or_rewritten(self):
        for config in [None, make_config('scheduled'), make_config('immediate'), make_config('none')]:
            a = Activity.objects.create(host=self.host, title='Old opportunity', participation_config=config,
                                        available_responses=['interested','question'], cost_type='paid', cost_amount=25)
            ActivityInvitation.objects.create(activity=a,user=self.viewer,invited_by=self.host)
            history = ActivityResponse.objects.create(activity=a,user=self.viewer,status='interested',note='Keep history')
            snapshot = ActivityResponse.objects.values().get(pk=history.pk)
            old = Activity.objects.values().get(pk=a.pk)
            self.assertContains(self.client.get(a.get_absolute_url()), 'Interested (historical)')
            self.client.get('/?q=Old')
            self.assertEqual(Activity.objects.values().get(pk=a.pk), old)
            self.assertEqual(ActivityResponse.objects.values().get(pk=history.pk), snapshot)
            if config:
                self.post(a,'confirm_attendance')
                self.assertEqual(ActivityResponse.objects.values().get(pk=history.pk), snapshot)
            a.participation_config = make_config('scheduled', version=2); a.cost_type='free'; a.cost_amount=None
            with self.assertRaises(ValidationError): a.save()

    def test_series_defaults_copy_version_and_actions_without_affecting_occurrences(self):
        s = ActivitySeries.objects.create(owner=self.host,title='Scheduled series',description='Together',cost_type='free',
                participation_config=make_config('scheduled',version=2),available_responses=['interested','vote'])
        initial = occurrence_initial(s)
        form = ActivityForm({'title':'Copy','description':'Together','audience':'everyone','location_type':'tbd',
                'cost_type':'free','participation_pattern':'scheduled'},user=self.host,context_series=s,initial=initial)
        self.assertTrue(form.is_valid(), form.errors)
        a = form.save(commit=False); a.host=self.host; a.save()
        old = deepcopy(a.participation_config)
        form = ActivitySeriesForm({'title':s.title,'description':s.description,'audience':'everyone','location_type':'tbd',
                'cost_type':'free','cadence':'flexible','participation_pattern':'immediate'},instance=s,user=self.host)
        self.assertTrue(form.is_valid(),form.errors); s=form.save()
        a.refresh_from_db(); self.assertEqual(a.participation_config,old)
        self.assertEqual(s.available_responses,['interested','vote'])
        next_initial = occurrence_initial(s)
        self.assertEqual(next_initial['participation_config'],make_config('immediate',version=2))
        next_initial['participation_config']['actions'].append('open_external')
        self.assertNotIn('open_external',s.participation_config['actions'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
    def test_email_acceptance_requests_pattern_action_but_creates_no_response_or_group_join(self):
        for pattern, prompt in [('scheduled','Confirm attendance below'),('immediate','Join now below')]:
            a = self.activity(pattern)
            request = RequestFactory().post('/', REMOTE_ADDR='192.0.2.5')
            self.assertTrue(issue_invitation(a,self.host,self.viewer.email,request))
            token = re.search('/activity-invitations/([^/]+)/',mail.outbox[-1].body).group(1)
            url = reverse('activities:email_invitation',args=[token])
            self.assertContains(self.client.get(url),prompt)
            self.assertNotContains(self.client.get(url), 'no response is required')
            anonymous = Client().get(url)
            self.assertNotContains(anonymous,a.title); self.assertNotContains(anonymous,prompt)
            self.assertRedirects(self.client.post(url),a.get_absolute_url())
            self.assertTrue(ActivityInvitation.objects.filter(activity=a,user=self.viewer).exists())
            self.assertFalse(ActivityResponse.objects.filter(activity=a).exists())
            self.assertFalse(GroupMembership.objects.filter(user=self.viewer).exists())

    def test_notification_recipient_authority_stays_existing_responses_and_consent(self):
        for pattern, action in [('scheduled','confirm_attendance'),('immediate','join_now')]:
            a = self.activity(pattern)
            self.post(a,action)
            ActivityInvitation.objects.create(activity=a,user=self.other,invited_by=self.host)
            event = queue_event(a,self.host,'cancellation')
            self.assertEqual(list(ActivityNotificationDelivery.objects.filter(event=event).values_list('recipient_id','status')),[(self.viewer.pk,'pending')])
            change_response(a.pk,self.viewer,remove=True)
            from .notifications import eligibility
            self.assertEqual(eligibility(event,self.viewer),'recipient_no_response')


class PatternConcurrencyTests(SimpleTestCase):
    def test_file_backed_last_seat_and_cancellation_races_for_both_patterns(self):
        with tempfile.TemporaryDirectory() as root:
            env = {**os.environ, 'DJANGO_SETTINGS_MODULE':'belong.settings','BELONG_ENV':'test',
                'DJANGO_DB_PATH':str(Path(root)/'patterns.sqlite3'),'DJANGO_ALLOWED_HOSTS':'testserver'}
            code = '''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.management import call_command
from django.db import connections
from django.test import Client
from django.urls import reverse
from belong.test_helpers import create_legacy_user
from activities.models import Activity, ActivityResponse, ActivityInvitation
from activities.participation_config import make_config
call_command('migrate',verbosity=0)
users=[create_legacy_user('race-'+str(i)) for i in range(5)]
clients=[]
for user in users:
    c=Client();c.force_login(user);clients.append(c)
for pattern,action in [('scheduled','confirm_attendance'),('immediate','join_now')]:
    for iteration in range(3):
        a=Activity.objects.create(host=users[0],title='Last seat',cost_type='free',capacity=1,participation_config=make_config(pattern,version=2))
        ActivityInvitation.objects.create(activity=a,user=users[1],invited_by=users[0])
        barrier=Barrier(4)
        def join(i):
            barrier.wait(timeout=10)
            try:
                r=clients[i].post(reverse('activities:respond',args=[a.pk]),{'action':action})
                assert r.status_code==200,r.status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(join,range(1,5)))
        assert ActivityResponse.objects.filter(activity=a,status='committed').count()==1
    for iteration in range(3):
        a=Activity.objects.create(host=users[0],title='Cancel race',cost_type='free',capacity=1,participation_config=make_config(pattern,version=2))
        barrier=Barrier(2)
        def cancel_or_join(i):
            barrier.wait(timeout=10)
            try:
                route='cancel' if i==0 else 'respond'
                r=clients[i].post(reverse('activities:'+route,args=[a.pk]),{'action':action,'reason':'Closed'})
                assert r.status_code==(302 if i==0 else 200),r.status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(cancel_or_join,range(2)))
        a.refresh_from_db();assert a.is_cancelled
        assert all(r.updated_at<=a.cancelled_at for r in a.responses.all())
        before=list(a.responses.values())
        clients[1].post(reverse('activities:respond',args=[a.pk]),{'action':action})
        clients[1].post(reverse('activities:leave',args=[a.pk]))
        assert list(a.responses.values())==before
'''
            result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
