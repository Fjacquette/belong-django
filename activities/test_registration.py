"""Registration eligibility, explicit free allocation and preservation boundaries."""
from decimal import Decimal
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404
from django.test import TestCase, SimpleTestCase, TransactionTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from social.models import Friendship
from groups.models import Group, GroupMembership
from .models import (Activity, ActivitySeries, ActivityResponse, ActivityInvitation, RegistrationTarget,
    RegistrationRequest, RegistrationAdmission, FreeRegistration, RegistrationPlace, OngoingOpportunity,
    EnrollmentRequest, AdmissionDecision, OngoingEnrollment, CohortPlace, ActivityNotificationEvent,
    Announcement, GroupJoinOffer)
from .forms import ActivityForm, ActivitySeriesForm
from .participation_config import make_config, validate_config
from .participation import change_response, cancel_activity
from .registration import mutate, registrations_for, facts
from .polls import recipient_ids
from .notifications import queue_event


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('d2-host')
        cls.alice = create_legacy_user('d2-alice')
        cls.bob = create_legacy_user('d2-bob')
        cls.other = create_legacy_user('d2-other')

    def fixture(self, *, admission='open', allocation='claim', amount=0, capacity=1, audience='everyone'):
        activity = Activity.objects.create(host=self.host, title='D2 class', audience=audience,
            cost_type='paid' if amount else 'free', cost_amount=amount or None,
            participation_config=make_config('registration', version=5))
        target = RegistrationTarget.objects.create(activity=activity, admission=admission,
            allocation=allocation, amount=amount, capacity=capacity)
        return activity, target

    def submit(self, activity, user=None, previous=''):
        mutate(activity.pk, user or self.alice, 'submit', version='1', request_id=previous)
        return activity.registration_target.requests.filter(user=user or self.alice).last()

    def act(self, activity, application, action='claim', user=None, decision=None):
        return mutate(activity.pk, user or self.alice, action, version='1', request_id=application.pk, decision=decision)

    def test_creation_requires_explicit_supported_terms_and_exact_quote(self):
        self.client.force_login(self.host)
        data = dict(title='D2 paid class', description='Terms', cost_type='paid', cost_amount='12.50',
            audience='everyone', location_type='tbd', participation_pattern='registration', capacity='12',
            registration_admission='request', registration_allocation='claim', available_responses=['committed'],
            currency='EUR', amount='0', version='999')
        response = self.client.post(reverse('activities:create'), data)
        activity = Activity.objects.latest('pk')
        self.assertRedirects(response, activity.get_absolute_url())
        target = activity.registration_target
        self.assertEqual((target.currency, target.amount, target.version, target.capacity), ('USD', Decimal('12.50'), 1, 12))
        self.assertEqual((target.admission, target.allocation), ('request', 'claim'))
        self.assertIsNone(activity.capacity)
        self.assertEqual(activity.available_responses, [])
        self.assertFalse(RegistrationRequest.objects.exists())
        for change in [dict(cost_amount=''), dict(cost_type='unknown'), dict(capacity='0'), dict(registration_admission='fake'), dict(registration_allocation='approval')]:
            form = ActivityForm({**data, **change}, user=self.host)
            self.assertFalse(form.is_valid(), change)
        for admission in ['open', 'invitation']:
            form = ActivityForm({**data, 'cost_type':'free', 'cost_amount':'', 'registration_allocation':'approval', 'registration_admission':admission}, user=self.host)
            self.assertFalse(form.is_valid())
        self.assertNotIn('registration', dict(ActivitySeriesForm(user=self.host).fields['participation_pattern'].choices))
        with self.assertRaises(ValidationError):
            ActivitySeries.objects.create(owner=self.host, title='No registration Series', participation_config=make_config('registration', version=5))

    def test_old_registration_navigation_and_invalid_versions_remain_fail_closed(self):
        old = Activity.objects.create(host=self.host, title='Legacy registration', participation_config=make_config('registration'))
        self.client.force_login(self.alice)
        self.assertContains(self.client.get(old.get_absolute_url()), 'No response required')
        for config in [dict(version=5, pattern='ongoing', actions=['view_details','register']), dict(version=5, pattern='registration', actions=['view_details']), dict(version=5, pattern='registration', actions=['view_details','pay'])]:
            with self.assertRaises(ValidationError): validate_config(config)
        with self.assertRaises(ValidationError):
            old.participation_config = make_config('registration', version=5); old.save()

    def test_submit_get_invitation_and_legacy_posts_are_never_confirmation(self):
        activity, target = self.fixture()
        ActivityInvitation.objects.create(activity=activity, user=self.alice, invited_by=self.host)
        self.client.force_login(self.alice)
        for path in [activity.get_absolute_url(), '/?q=D2']:
            self.assertEqual(self.client.get(path).status_code, 200)
        for route in ['respond','join','leave']:
            self.client.post(reverse('activities:'+route,args=[activity.pk]),dict(status='committed',action='register',variant='detail'))
        self.assertFalse(RegistrationRequest.objects.exists())
        first = self.submit(activity); self.submit(activity)
        self.assertEqual(target.requests.count(), 1)
        self.assertFalse(FreeRegistration.objects.exists()); self.assertFalse(RegistrationPlace.objects.exists())
        self.assertFalse(ActivityResponse.objects.exists()); self.assertFalse(GroupJoinOffer.objects.exists())
        self.assertEqual(recipient_ids(activity), set())
        self.assertEqual(facts(first, activity)['state'], 'Eligible — place not secured')
        self.assertContains(self.client.get('/?q=D2'), 'Eligible / View')
        self.act(activity, first)
        self.assertContains(self.client.get('/?q=D2'), 'Registered / View')

    def test_open_free_claim_capacity_withdrawal_history_and_new_request_identity(self):
        activity, target = self.fixture()
        alice = self.submit(activity); bob = self.submit(activity, self.bob)
        self.act(activity, alice); self.act(activity, alice)
        self.assertEqual(FreeRegistration.objects.count(), 1)
        self.assertIn('Full', self.act(activity, bob, user=self.bob))
        self.assertEqual(recipient_ids(activity), {self.alice.pk})
        self.act(activity, alice, 'withdraw'); self.act(activity, alice, 'withdraw')
        self.act(activity, bob, user=self.bob)
        self.assertEqual(recipient_ids(activity), {self.bob.pk})
        self.assertEqual(RegistrationPlace.objects.filter(released_at__isnull=True).count(), 1)
        again = self.submit(activity, previous=alice.pk)
        self.assertNotEqual(again.pk, alice.pk)
        self.act(activity, alice, 'withdraw')
        again.refresh_from_db(); self.assertIsNone(again.closed_at)
        self.assertEqual(target.requests.count(), 3)
        self.assertEqual(FreeRegistration.objects.count(), 2)
        self.assertFalse(ActivityResponse.objects.exists())

    def test_approval_only_eligibility_never_allocates_even_when_full(self):
        activity, target = self.fixture(admission='request')
        alice = self.submit(activity); bob = self.submit(activity, self.bob)
        self.assertIn('not currently satisfied', self.act(activity, alice))
        for row in [alice, bob]:
            self.act(activity, row, 'decide', user=self.host, decision='approved')
        self.assertFalse(RegistrationPlace.objects.exists()); self.assertFalse(FreeRegistration.objects.exists())
        alice.refresh_from_db(); self.assertEqual(facts(alice, activity)['state'], 'Eligible — place not secured')
        self.act(activity, alice)
        self.assertIn('Full', self.act(activity, bob, user=self.bob))
        self.assertEqual(RegistrationAdmission.objects.filter(result='approved').count(), 2)
        self.assertEqual(registrations_for(activity).count(), 1)

    def test_approval_allocation_is_atomic_full_keeps_pending_and_unlimited_needs_no_place_row(self):
        activity, target = self.fixture(admission='request', allocation='approval')
        alice = self.submit(activity); bob = self.submit(activity, self.bob)
        self.act(activity, alice, 'decide', user=self.host, decision='approved')
        self.assertIn('Full', self.act(activity, bob, 'decide', user=self.host, decision='approved'))
        self.assertFalse(RegistrationAdmission.objects.filter(request=bob).exists())
        self.assertEqual(registrations_for(activity).count(), 1)
        self.act(activity, alice, 'decide', user=self.host, decision='denied')
        self.assertEqual(RegistrationAdmission.objects.get(request=alice).result, 'approved')
        unlimited, pool = self.fixture(admission='request', allocation='approval', capacity=None)
        row = self.submit(unlimited)
        self.act(unlimited, row, 'decide', user=self.host, decision='approved')
        self.assertEqual(registrations_for(unlimited).count(), 1)
        self.assertFalse(RegistrationPlace.objects.filter(confirmation__request__target=pool).exists())

    def test_paid_open_request_invitation_quotes_never_confirm_or_capture(self):
        for admission in ['open','request','invitation']:
            activity, target = self.fixture(admission=admission, amount=20)
            if admission == 'invitation': ActivityInvitation.objects.create(activity=activity,user=self.alice,invited_by=self.host)
            row = self.submit(activity)
            if admission == 'request': self.act(activity,row,'decide',user=self.host,decision='approved')
            self.assertIn('Payments are unavailable', self.act(activity,row))
            row.refresh_from_db()
            self.assertEqual(facts(row,activity)['state'],'Eligible — payment required')
            self.assertEqual(recipient_ids(activity),set())
            self.client.force_login(self.alice)
            page=self.client.get(activity.get_absolute_url())
            self.assertContains(page,'USD 20.00');self.assertContains(page,'Payments are unavailable')
            self.assertNotContains(page,'Claim free place'); self.assertNotContains(page,'Place: Secured')
            self.assertContains(self.client.get('/?q=D2'), 'Payment required / View')
        self.assertFalse(FreeRegistration.objects.exists());self.assertFalse(RegistrationPlace.objects.exists());self.assertFalse(ActivityResponse.objects.exists())

    def test_invitation_required_scoped_action_time_and_secured_entitlement_survives_revoke(self):
        activity,target=self.fixture(admission='invitation')
        unrelated,_=self.fixture()
        ActivityInvitation.objects.create(activity=unrelated,user=self.alice,invited_by=self.host)
        self.assertIsNone(self.submit(activity))
        invitation=ActivityInvitation.objects.create(activity=activity,user=self.alice,invited_by=self.host)
        row=self.submit(activity); invitation.delete()
        self.assertIn('not currently satisfied',self.act(activity,row))
        invitation=ActivityInvitation.objects.create(activity=activity,user=self.alice,invited_by=self.host)
        self.act(activity,row);invitation.delete()
        self.assertEqual(registrations_for(activity).count(),1)
        self.assertEqual(facts(row,activity)['state'],'Registered')
        self.act(activity,row,'withdraw');self.assertFalse(registrations_for(activity).exists())
        self.assertFalse(GroupMembership.objects.exists())

    def test_audience_is_independent_of_invitation_and_lost_access_blocks_approval(self):
        activity,target=self.fixture(admission='request',audience='friends')
        ActivityInvitation.objects.create(activity=activity,user=self.alice,invited_by=self.host)
        with self.assertRaises(Http404):self.submit(activity)
        friend=Friendship.objects.create(user_a=self.host,user_b=self.alice)
        row=self.submit(activity);friend.delete()
        self.assertIn('cannot currently access',self.act(activity,row,'decide',user=self.host,decision='approved'))
        self.assertFalse(RegistrationAdmission.objects.exists())
        self.client.force_login(self.alice);self.assertEqual(self.client.get(activity.get_absolute_url()).status_code,404)

    def test_auth_policy_csrf_method_and_request_scope(self):
        activity,target=self.fixture(admission='request');row=self.submit(activity)
        for action,user in [('decide',self.bob),('withdraw',self.bob),('claim',self.bob)]:
            with self.assertRaises(Http404):self.act(activity,row,action,user=user,decision='approved')
        foreign,_=self.fixture()
        with self.assertRaises(Http404):self.act(foreign,row)
        mutate(activity.pk,self.alice,'withdraw',version='999',request_id=row.pk)
        row.refresh_from_db();self.assertIsNone(row.closed_at)
        self.client.force_login(self.alice)
        route=reverse('activities:registration_action',args=[activity.pk,'submit'])
        self.assertEqual(self.client.get(route).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.alice)
        self.assertEqual(csrf.post(route,{'policy':'1'}).status_code,403)
        self.assertEqual(self.client.post(reverse('activities:registration_action',args=[activity.pk,'pay']),{'policy':'1'}).status_code,404)

    def test_group_organizer_role_and_optional_group_invitation_scope(self):
        activity, target = self.fixture(admission='request')
        group = Group.objects.create(owner=self.host, name='Optional class', access='closed')
        membership = GroupMembership.objects.create(group=group, user=self.bob, role='organizer', status='active')
        activity.group=group;activity.save()
        row=self.submit(activity)
        self.act(activity,row,'decide',user=self.bob,decision='approved')
        self.assertFalse(GroupMembership.objects.filter(group=group,user=self.alice).exists())
        membership.role='member';membership.save()
        another=self.submit(activity,self.other)
        with self.assertRaises(Http404):self.act(activity,another,'decide',user=self.bob,decision='approved')
        invited,pool=self.fixture(admission='invitation')
        invited.group=group;invited.invite_group_members=True;invited.save()
        application=self.submit(invited,self.bob)
        membership.status='pending';membership.save()
        self.assertIn('not currently satisfied',self.act(invited,application,user=self.bob))
        self.assertFalse(FreeRegistration.objects.exists())

    def test_denial_is_retained_and_resubmission_requires_current_request(self):
        activity,target=self.fixture(admission='request');row=self.submit(activity)
        self.act(activity,row,'decide',user=self.host,decision='denied')
        self.submit(activity)
        self.assertEqual(target.requests.count(),1)
        again=self.submit(activity,previous=row.pk)
        self.assertNotEqual(again.pk,row.pk)
        self.assertEqual(RegistrationAdmission.objects.get(request=row).result,'denied')
        self.assertFalse(FreeRegistration.objects.exists())

    def test_htmx_native_return_private_history_and_roster_facts(self):
        activity,target=self.fixture(admission='request');alice=self.submit(activity);bob=self.submit(activity,self.bob)
        self.act(activity,alice,'decide',user=self.host,decision='approved')
        self.client.force_login(self.alice)
        path='/?q=D2&audience=everyone&audience=friends&cost=free'
        route=reverse('activities:registration_action',args=[activity.pk,'claim'])
        page=self.client.post(route,dict(policy='1',request=alice.pk,variant='detail',next=path),HTTP_HX_REQUEST='true')
        self.assertContains(page,'You: Registered');self.assertContains(page,'Place: Secured');self.assertContains(page,'name="next" value="/?q=D2&amp;audience=everyone&amp;audience=friends&amp;cost=free"')
        page=self.client.get(activity.get_absolute_url());self.assertEqual(len(page.context['registration_rows']),1)
        response=self.client.post(reverse('activities:registration_action',args=[activity.pk,'withdraw']),dict(policy='1',request=alice.pk,next=path))
        self.assertEqual(response.url,path)
        self.client.force_login(self.host)
        page=self.client.get(reverse('activities:roster',args=[activity.pk]));self.assertContains(page,'Approve eligibility');self.assertContains(page,'Place: Released');self.assertEqual(len(page.context['registration_rows']),2)
        self.assertNotContains(page,'No response required')

    def test_terms_and_quote_immutable_and_db_duplicate_request_guard(self):
        activity,target=self.fixture(amount=10)
        for name,value in [('amount',11),('admission','request'),('allocation','approval'),('version',2),('capacity',2),('currency','EUR')]:
            row=RegistrationTarget.objects.get(pk=target.pk);setattr(row,name,value)
            with self.assertRaises(ValidationError):row.save()
        row=self.submit(activity)
        with self.assertRaises(IntegrityError),transaction.atomic():RegistrationRequest.objects.create(target=target,user=self.alice)
        activity.cost_amount=999;activity.save()
        self.client.force_login(self.alice)
        page=self.client.get(activity.get_absolute_url());self.assertContains(page,'USD 10.00')
        self.assertEqual(row.target_id,target.pk)
        other,other_target=self.fixture(amount=10)
        row.target=other_target
        with self.assertRaises(ValidationError):row.save()
        with self.assertRaises(ValidationError):FreeRegistration.objects.create(request=RegistrationRequest.objects.get(pk=row.pk))

    def test_cancellation_freezes_history_and_only_confirmed_free_subscribes(self):
        activity,target=self.fixture();alice=self.submit(activity);bob=self.submit(activity,self.bob)
        self.act(activity,alice)
        self.assertEqual(recipient_ids(activity),{self.alice.pk})
        before=list(RegistrationRequest.objects.values())
        cancel_activity(activity.pk,self.host,'Stopped')
        for action in ['claim','withdraw','submit']:self.assertIn('Cancelled',self.act(activity,alice,action))
        self.assertEqual(list(RegistrationRequest.objects.values()),before)
        self.assertEqual(recipient_ids(activity),{self.alice.pk})
        self.client.force_login(self.alice)
        page=self.client.get(activity.get_absolute_url());self.assertContains(page,'before cancellation');self.assertNotContains(page,'Withdraw registration</button>')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BELONG_PUBLIC_ORIGIN='https://belong.example')
    def test_email_adapter_never_subscribes_pending_eligible_or_paid_and_respects_optin(self):
        for user in [self.host,self.alice,self.bob]:
            user.email=user.username+'@example.invalid';user.save()
            user.profile.email_verified_at=timezone.now();user.profile.activity_email_enabled=True;user.profile.save()
        activity,target=self.fixture();alice=self.submit(activity);self.submit(activity,self.bob)
        with self.captureOnCommitCallbacks(execute=True):self.act(activity,alice)
        self.assertEqual(len(mail.outbox),0)
        ann=Announcement.objects.create(activity=activity,author=self.host,body='Private logistics')
        with self.captureOnCommitCallbacks(execute=True):queue_event(activity,self.host,'update',announcement=ann)
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,[self.alice.email])
        self.assertNotIn('Private logistics',mail.outbox[0].body);self.assertIn('Activity you registered for',mail.outbox[0].body)
        self.act(activity,alice,'withdraw')
        with self.captureOnCommitCallbacks(execute=True):cancel_activity(activity.pk,self.host,'Stopped')
        self.assertEqual(len(mail.outbox),1)
        paid,_=self.fixture(amount=10);self.submit(paid)
        with self.captureOnCommitCallbacks(execute=True):cancel_activity(paid.pk,self.host,'Stopped')
        self.assertFalse(ActivityNotificationEvent.objects.get(activity=paid).deliveries.exists())


class RegistrationMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_d1_enrollment_and_legacy_data_without_backfill(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes();old=[('activities','0026_enrollmentrequest_ongoingenrollment_cohortplace_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            u=apps.get_model('auth','User').objects.create(username='d2-migration')
            activity=apps.get_model('activities','Activity').objects.create(host_id=u.pk,title='Ongoing',participation_config=make_config('ongoing',version=4))
            pool=apps.get_model('activities','OngoingOpportunity').objects.create(activity_id=activity.pk,capacity=1)
            req=apps.get_model('activities','EnrollmentRequest').objects.create(opportunity_id=pool.pk,user_id=u.pk)
            apps.get_model('activities','AdmissionDecision').objects.create(request_id=req.pk,actor_id=u.pk,result='approved')
            enrollment=apps.get_model('activities','OngoingEnrollment').objects.create(request_id=req.pk)
            apps.get_model('activities','CohortPlace').objects.create(enrollment_id=enrollment.pk)
            apps.get_model('activities','ActivityResponse').objects.create(activity_id=activity.pk,user_id=u.pk,status='interested',note='Retain')
            names=['Activity','OngoingOpportunity','EnrollmentRequest','AdmissionDecision','OngoingEnrollment','CohortPlace','ActivityResponse']
            before={name:list(apps.get_model('activities',name).objects.values()) for name in names}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as current
            for name,rows in before.items():self.assertEqual(list(current.get_model('activities',name).objects.values()),rows,name)
            self.assertFalse(RegistrationTarget.objects.exists());self.assertFalse(RegistrationRequest.objects.exists())
        finally:MigrationExecutor(connection).migrate(leaves)


class RegistrationRaceTests(SimpleTestCase):
    def test_file_backed_last_seat_approval_claim_withdraw_cancel_and_duplicate_submission_races(self):
        script=r'''
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','belong.settings');django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.core.management import call_command
from belong.test_helpers import create_legacy_user
from activities.models import *
from activities.participation_config import make_config
from activities.registration import mutate,registrations_for
from activities.participation import cancel_activity
call_command('migrate',verbosity=0)
u=[create_legacy_user('d2-race-'+str(n)) for n in range(5)]
def parallel(actions):
 barrier=Barrier(len(actions))
 def run(action):
  close_old_connections()
  try:barrier.wait(timeout=10);action()
  finally:close_old_connections()
 with ThreadPoolExecutor(max_workers=len(actions)) as pool:list(pool.map(run,actions))
def fixture(admission='open',allocation='claim'):
 a=Activity.objects.create(host=u[0],title='Race',cost_type='free',participation_config=make_config('registration',version=5))
 t=RegistrationTarget.objects.create(activity=a,admission=admission,allocation=allocation,amount=0,capacity=1)
 for user in u[1:]:mutate(a.pk,user,'submit',version='1')
 return a,t,list(t.requests.all())
for attempt in range(3):
 a,t,rows=fixture()
 parallel([lambda:mutate(a.pk,u[1],'submit',version='1'),lambda:mutate(a.pk,u[1],'submit',version='1')])
 assert t.requests.filter(user=u[1]).count()==1
 parallel([lambda row=row:mutate(a.pk,row.user,'claim',version='1',request_id=row.pk) for row in rows])
 assert registrations_for(a).count()==1
 assert RegistrationPlace.objects.filter(confirmation__request__target=t,released_at__isnull=True).count()==1
 a,t,rows=fixture('request','approval')
 parallel([lambda row=row:mutate(a.pk,u[0],'decide',version='1',request_id=row.pk,decision='approved') for row in rows])
 assert registrations_for(a).count()==1
 assert RegistrationAdmission.objects.filter(request__target=t).count()==1
 a,t,rows=fixture()
 parallel([lambda:mutate(a.pk,u[1],'claim',version='1',request_id=rows[0].pk),lambda:mutate(a.pk,u[1],'withdraw',version='1',request_id=rows[0].pk)])
 assert registrations_for(a).count()==0
 assert RegistrationPlace.objects.filter(confirmation__request__target=t,released_at__isnull=True).count()==0
 a,t,rows=fixture()
 parallel([lambda:mutate(a.pk,u[1],'claim',version='1',request_id=rows[0].pk),lambda:cancel_activity(a.pk,u[0],'Stop')])
 a.refresh_from_db();assert a.is_cancelled
 confirmation=FreeRegistration.objects.filter(request=rows[0]).first()
 assert confirmation is None or confirmation.created_at <= a.cancelled_at
 assert ActivityResponse.objects.count()==0
print('D2 races passed')
'''
        with tempfile.TemporaryDirectory() as root:
            env=os.environ.copy();env.update(BELONG_ENV='test',DJANGO_DB_PATH=str(Path(root)/'race.sqlite3'),EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
            result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('D2 races passed',result.stdout)
