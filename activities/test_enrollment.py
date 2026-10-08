"""D1: request, admission, ongoing enrollment and limited places are separate."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, SimpleTestCase, TransactionTestCase, Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from social.models import Friendship
from .models import (Activity, ActivityInvitation, ActivityResponse, ActivitySeries, OngoingOpportunity,
    EnrollmentRequest, AdmissionDecision, OngoingEnrollment, CohortPlace, GroupJoinOffer,
    ActivityNotificationEvent, ActivityNotificationDelivery, Announcement)
from .forms import ActivityForm, ActivitySeriesForm
from .participation_config import make_config, validate_config
from .enrollment import request_place, decide_request, withdraw_request, enrollment_recipients
from .participation import change_response, cancel_activity
from .announcements import updates_for
from .notifications import queue_event


class FreeEnrollmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('jan')
        cls.alice = create_legacy_user('alice')
        cls.bob = create_legacy_user('bob')
        cls.outsider = create_legacy_user('outsider')

    def setUp(self):
        self.activity = Activity.objects.create(host=self.host, title='Ongoing D&D', cost_type='free',
            participation_config=make_config('ongoing', version=4))
        self.pool = OngoingOpportunity.objects.create(activity=self.activity, capacity=1)
        self.client.force_login(self.alice)

    def apply(self, user=None, previous=''):
        request_place(self.activity.pk, user or self.alice, previous=previous)
        return EnrollmentRequest.objects.filter(opportunity=self.pool, user=user or self.alice).last()

    def approve(self, application):
        return decide_request(self.activity.pk, self.host, application.pk, 'approved')

    def test_creator_explicit_free_pattern_and_separate_player_limit(self):
        self.client.force_login(self.host)
        data = {'title':'Ongoing game','description':'Weekly D&D','cost_type':'free','location_type':'tbd',
                'audience':'everyone','participation_pattern':'ongoing','capacity':'5',
                'available_responses':['committed'],'policy':'eligibility_only'}
        response = self.client.post(reverse('activities:create'), data)
        a = Activity.objects.latest('pk')
        self.assertRedirects(response, a.get_absolute_url())
        self.assertEqual(a.participation_config, make_config('ongoing', version=4))
        self.assertIsNone(a.capacity); self.assertEqual(a.ongoing.capacity, 5)
        self.assertEqual(a.ongoing.policy, 'approval_secures_place')
        self.assertEqual(a.available_responses, [])
        self.assertFalse(ActivityResponse.objects.exists()); self.assertFalse(EnrollmentRequest.objects.exists())
        for values in [{'cost_type':'paid','cost_amount':'10'}, {'cost_type':'unknown'}, {'capacity':'0'}]:
            form = ActivityForm({**data, **values}, user=self.host)
            self.assertFalse(form.is_valid(), values)
        self.assertNotIn('ongoing', dict(ActivitySeriesForm(user=self.host).fields['participation_pattern'].choices))
        with self.assertRaises(ValidationError):
            ActivitySeries.objects.create(owner=self.host, title='Unsupported cohort default', cost_type='free', participation_config=make_config('ongoing', version=4))

    def test_version_one_ongoing_remains_navigation_and_only_new_version_enables_requests(self):
        old = Activity.objects.create(host=self.host, title='Old ongoing', participation_config=make_config('ongoing'))
        self.assertContains(self.client.get(old.get_absolute_url()), 'No response required')
        self.assertFalse(old.is_free_ongoing)
        for config in [{'version':4,'pattern':'scheduled','actions':['view_details','request_enrollment']},
                       {'version':4,'pattern':'ongoing','actions':['view_details','confirm_attendance']},
                       {'version':4,'pattern':'ongoing','actions':['view_details']}]:
            with self.assertRaises(ValidationError): validate_config(config)
        with self.assertRaises(ValidationError):
            old.participation_config = make_config('ongoing', version=4); old.save()

    def test_get_invitation_and_legacy_rsvp_posts_never_enroll_or_consume_places(self):
        ActivityInvitation.objects.create(activity=self.activity, user=self.alice, invited_by=self.host)
        for path in ['/?q=Ongoing', self.activity.get_absolute_url()]:
            r = self.client.get(path); self.assertContains(r, 'Request a player place')
            self.assertNotContains(r, "I'm coming")
        for name in ['respond','join','leave']:
            self.client.post(reverse('activities:'+name, args=[self.activity.pk]),
                {'status':'committed','action':'request_enrollment','variant':'detail'}, HTTP_HX_REQUEST='true')
        self.assertFalse(EnrollmentRequest.objects.exists()); self.assertFalse(ActivityResponse.objects.exists())
        self.assertFalse(CohortPlace.objects.exists()); self.assertFalse(GroupMembership.objects.exists())

    def test_request_is_pending_idempotent_and_never_waitlist_or_attendance(self):
        a = self.apply(); self.apply()
        self.assertEqual(EnrollmentRequest.objects.count(), 1)
        self.assertFalse(AdmissionDecision.objects.exists()); self.assertFalse(OngoingEnrollment.objects.exists())
        self.assertFalse(CohortPlace.objects.exists()); self.assertFalse(GroupJoinOffer.objects.exists())
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'You: Request sent')
        self.assertContains(self.client.get('/?q=Ongoing'), 'Request sent / View')
        self.assertEqual(enrollment_recipients(self.activity), set())

    def test_approval_secures_one_place_and_full_request_stays_pending(self):
        alice = self.apply(); bob = self.apply(self.bob)
        self.assertIn('Approved and enrolled', self.approve(alice))
        self.approve(alice)
        self.assertIn('full', self.approve(bob))
        self.assertEqual(AdmissionDecision.objects.count(), 1)
        self.assertFalse(hasattr(bob, 'decision'))
        self.assertEqual(OngoingEnrollment.objects.count(), 1); self.assertEqual(CohortPlace.objects.count(), 1)
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertEqual(enrollment_recipients(self.activity), {self.alice.pk})
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'You: Enrolled')

    def test_withdraw_releases_place_and_keeps_approval_then_new_request_has_new_identity(self):
        a = self.apply(); self.approve(a)
        decision = AdmissionDecision.objects.get(request=a); enrollment = OngoingEnrollment.objects.get(request=a)
        place = CohortPlace.objects.get(enrollment=enrollment)
        withdraw_request(self.activity.pk, self.alice, a.pk)
        withdraw_request(self.activity.pk, self.alice, a.pk)
        self.assertEqual(AdmissionDecision.objects.get(pk=decision.pk).result, 'approved')
        enrollment.refresh_from_db(); place.refresh_from_db(); a.refresh_from_db()
        self.assertIsNotNone(enrollment.ended_at); self.assertIsNotNone(place.released_at); self.assertIsNotNone(a.withdrawn_at)
        self.assertEqual(enrollment_recipients(self.activity), set())
        b = self.apply(self.bob); self.approve(b)
        new = self.apply(previous=a.pk); self.assertNotEqual(new.pk, a.pk)
        self.assertIn('full', self.approve(new))
        withdraw_request(self.activity.pk, self.alice, a.pk)  # stale withdrawal cannot close new request
        new.refresh_from_db(); self.assertIsNone(new.closed_at)
        self.assertEqual(self.pool.requests.filter(user=self.alice).count(), 2)

    def test_deny_retains_decision_and_person_may_request_again(self):
        a = self.apply(); decide_request(self.activity.pk, self.host, a.pk, 'denied')
        a.refresh_from_db(); self.assertIsNotNone(a.closed_at)
        self.assertIsNone(a.withdrawn_at); self.assertFalse(CohortPlace.objects.exists())
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'You: Request denied')
        self.assertIn('already decided', self.approve(a))
        new = self.apply(previous=a.pk); self.assertNotEqual(a.pk, new.pk)
        self.approve(new)
        self.assertEqual(list(AdmissionDecision.objects.order_by('pk').values_list('result', flat=True)), ['denied','approved'])

    def test_pending_withdrawal_never_creates_decision_or_place_and_stale_resubmit_is_rejected(self):
        a = self.apply(); withdraw_request(self.activity.pk, self.alice, a.pk)
        self.assertFalse(AdmissionDecision.objects.exists()); self.assertFalse(OngoingEnrollment.objects.exists())
        request_place(self.activity.pk, self.alice)  # old form from before first request
        self.assertEqual(EnrollmentRequest.objects.count(), 1)
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'You: Withdrawn')
        self.assertIn('closed', self.approve(a))

    def test_unlimited_approval_requires_no_artificial_place_record(self):
        a = Activity.objects.create(host=self.host, title='Unlimited', cost_type='free', participation_config=make_config('ongoing', version=4))
        pool = OngoingOpportunity.objects.create(activity=a)
        for user in [self.alice, self.bob]:
            request_place(a.pk, user); application = pool.requests.get(user=user)
            decide_request(a.pk, self.host, application.pk, 'approved')
        self.assertEqual(enrollment_recipients(a), {self.alice.pk, self.bob.pk})
        self.assertFalse(CohortPlace.objects.exists())
        self.assertContains(self.client.get(a.get_absolute_url()), 'No player limit')

    def test_organizer_authorization_group_optional_and_membership_never_automatic(self):
        a = self.apply()
        self.client.force_login(self.outsider)
        url = reverse('activities:decide_enrollment', args=[self.activity.pk, a.pk])
        self.assertEqual(self.client.post(url, {'decision':'approved','policy':'1'}).status_code, 404)
        group = Group.objects.create(owner=self.host, name='Optional D&D', access='closed')
        GroupMembership.objects.create(group=group, user=self.bob, role='organizer', status='active')
        self.activity.group=group; self.activity.save(update_fields=['group'])
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(url, {'decision':'approved','policy':'1'}).status_code, 302)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.alice).exists())
        self.assertFalse(GroupJoinOffer.objects.exists())
        GroupMembership.objects.filter(group=group,user=self.bob).update(role='member')
        another = self.apply(self.outsider)
        self.assertEqual(self.client.post(reverse('activities:decide_enrollment',args=[self.activity.pk,another.pk]),
            {'decision':'denied','policy':'1'}).status_code, 404)

    def test_audience_checks_apply_to_requests_and_approval_and_lost_access_keeps_history(self):
        a = self.apply()
        self.activity.audience='friends'; self.activity.save(update_fields=['audience'])
        self.assertEqual(self.client.get(self.activity.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(reverse('activities:request_enrollment',args=[self.activity.pk]),{'policy':'1'}).status_code, 404)
        self.assertIn('cannot currently access', self.approve(a))
        self.assertFalse(AdmissionDecision.objects.exists())
        friendship=Friendship.objects.create(user_a=self.host,user_b=self.alice)
        self.approve(a); friendship.delete()
        self.assertEqual(enrollment_recipients(self.activity), {self.alice.pk})
        self.assertEqual(CohortPlace.objects.count(), 1)  # no silent loss of entitlement
        self.assertEqual(self.client.get(reverse('activities:roster',args=[self.activity.pk])).status_code,404)

    def test_wrong_methods_csrf_policy_forged_decisions_and_foreign_request_cannot_mutate(self):
        a = self.apply(self.bob)
        request_url = reverse('activities:request_enrollment',args=[self.activity.pk])
        self.assertEqual(self.client.get(request_url).status_code,405)
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.alice)
        self.assertEqual(strict.post(request_url,{'policy':'1'}).status_code,403)
        self.client.post(request_url, {'policy':'99','status':'approved'})
        self.assertEqual(EnrollmentRequest.objects.count(),1)
        self.assertEqual(self.client.post(reverse('activities:withdraw_enrollment',args=[self.activity.pk]),
            {'request':a.pk,'policy':'1'}).status_code,404)
        self.client.force_login(self.host)
        decision_url = reverse('activities:decide_enrollment',args=[self.activity.pk,a.pk])
        self.assertEqual(self.client.get(decision_url).status_code,405)
        self.assertEqual(self.client.post(decision_url,{'decision':'paid','policy':'1'}).status_code,404)
        self.client.post(decision_url,{'decision':'approved','policy':'99'})
        other = Activity.objects.create(host=self.host, title='Other pool', cost_type='free', participation_config=make_config('ongoing',version=4))
        OngoingOpportunity.objects.create(activity=other)
        self.assertEqual(self.client.post(reverse('activities:decide_enrollment',args=[other.pk,a.pk]),
            {'decision':'approved','policy':'1'}).status_code,404)
        self.assertFalse(AdmissionDecision.objects.exists())

    def test_cancel_freezes_ongoing_requests_and_history_but_not_meeting(self):
        a = self.apply(); b = self.apply(self.bob); self.approve(a)
        meeting = Activity.objects.create(host=self.host, title='Next meeting', ongoing_opportunity=self.pool,
            cost_type='free', participation_config=make_config('scheduled',version=2), capacity=1)
        cancel_activity(self.activity.pk, self.host, 'Game ended')
        self.assertIn('cancelled', self.approve(b))
        self.assertIn('cancelled', withdraw_request(self.activity.pk,self.alice,a.pk))
        self.assertIn('cancelled', request_place(self.activity.pk,self.outsider))
        self.assertEqual(CohortPlace.objects.filter(released_at__isnull=True).count(),1)
        self.assertFalse(meeting.is_cancelled)
        change_response(meeting.pk,self.bob,action='confirm_attendance')
        self.assertEqual(meeting.responses.get().user_id,self.bob.pk)
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'before cancellation')

    def test_separate_meeting_created_without_people_and_rsvp_withdrawal_does_not_change_pool(self):
        a = self.apply(); self.approve(a)
        self.activity.audience='friends';self.activity.save(update_fields=['audience'])
        Friendship.objects.create(user_a=self.host,user_b=self.alice)
        self.client.force_login(self.host)
        create = reverse('activities:create')+'?opportunity='+str(self.pool.pk)
        form = self.client.get(create).context['form']
        self.assertEqual(form.initial['participation_pattern'],'scheduled')
        self.assertEqual(form.initial['audience'],'friends')
        self.assertIsNone(form.initial.get('capacity'))
        data={'title':'Friday D&D','description':'First session','cost_type':'free','location_type':'tbd',
              'audience':'everyone','participation_pattern':'scheduled','capacity':'1'}
        response=self.client.post(create,data)
        meeting=Activity.objects.latest('pk'); self.assertRedirects(response,meeting.get_absolute_url())
        self.assertEqual(meeting.ongoing_opportunity_id,self.pool.pk);self.assertEqual(meeting.capacity,1)
        self.assertFalse(meeting.responses.exists()); self.assertFalse(meeting.direct_invitations.exists())
        change_response(meeting.pk,self.alice,action='confirm_attendance')
        change_response(meeting.pk,self.alice,remove=True)
        self.assertEqual(enrollment_recipients(self.activity),{self.alice.pk})
        change_response(meeting.pk,self.alice,action='confirm_attendance')
        withdraw_request(self.activity.pk,self.alice,a.pk)
        self.assertEqual(meeting.responses.get().status,'committed')
        self.assertNotContains(self.client.post(create,{**data,'participation_pattern':'ongoing'}), 'Activity created!')
        self.assertFalse(OngoingOpportunity.objects.filter(activity__ongoing_opportunity=self.pool).exists())
        self.client.force_login(self.bob); self.assertEqual(self.client.get(create).status_code,404)

    def test_private_source_not_disclosed_by_public_meeting_and_no_enrollment_gate_is_implied(self):
        self.activity.audience='friends';self.activity.save(update_fields=['audience'])
        meeting=Activity.objects.create(host=self.host,title='Public meeting',ongoing_opportunity=self.pool,
            cost_type='free',participation_config=make_config('scheduled',version=2))
        self.assertNotContains(self.client.get(meeting.get_absolute_url()),'Ongoing D&D')
        change_response(meeting.pk,self.alice,action='confirm_attendance')
        self.assertEqual(meeting.responses.count(),1);self.assertFalse(EnrollmentRequest.objects.exists())

    def test_htmx_and_native_filtered_returns_have_actual_enrollment_state(self):
        url=reverse('activities:request_enrollment',args=[self.activity.pk])
        context='/?q=D%26D&cost=free&cost=paid&audience=everyone'
        r=self.client.post(url,{'policy':'1','variant':'detail','next':context},HTTP_HX_REQUEST='true')
        self.assertContains(r,'You: Request sent');self.assertNotContains(r,'No response required')
        self.assertContains(r,'/?q=D%26D&amp;cost=free&amp;cost=paid&amp;audience=everyone')
        a=EnrollmentRequest.objects.get();self.approve(a)
        r=self.client.post(reverse('activities:withdraw_enrollment',args=[self.activity.pk]),
            {'policy':'1','request':a.pk,'variant':'detail','next':context})
        self.assertRedirects(r,context)
        r=self.client.post(url,{'policy':'1','request':a.pk,'variant':'card','next':'https://other.invalid/'},HTTP_HX_REQUEST='true')
        self.assertContains(r,'Request sent / View');self.assertNotContains(r,'https://other.invalid/')

    def test_routine_recipients_are_actual_enrollees_not_pending_requests_or_group_members(self):
        a=self.apply();self.apply(self.bob);self.approve(a)
        self.assertEqual(enrollment_recipients(self.activity),{self.alice.pk})
        self.client.force_login(self.host)
        url=reverse('activities:announce',args=[self.activity.pk])
        token=self.client.get(url).context['form'].initial['submission_token']
        r=self.client.post(url,{'body':'Next session logistics','submission_token':token})
        ann=Announcement.objects.get(activity=self.activity)
        self.assertEqual(set(ann.recipients.values_list('pk',flat=True)),{self.alice.pk})
        self.assertTrue(updates_for(self.activity,self.alice,organizer=False).exists())
        self.assertFalse(updates_for(self.activity,self.bob,organizer=False).exists())
        withdraw_request(self.activity.pk,self.alice,a.pk)
        self.assertFalse(updates_for(self.activity,self.alice,organizer=False).exists())
        self.assertFalse(ActivityResponse.objects.exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
    def test_enrollment_updates_and_cancellation_reuse_verified_optin_controls_without_approval_mail(self):
        for user in [self.host, self.alice, self.bob]:
            user.email = user.username+'@example.invalid'; user.save(update_fields=['email'])
            user.profile.email_verified_at=timezone.now();user.profile.activity_email_enabled=True;user.profile.save()
        a=self.apply();self.apply(self.bob)
        with self.captureOnCommitCallbacks(execute=True):self.approve(a)
        self.assertEqual(len(mail.outbox),0)
        ann=Announcement.objects.create(activity=self.activity,author=self.host,body='Private logistics')
        with self.captureOnCommitCallbacks(execute=True):queue_event(self.activity,self.host,'update',announcement=ann)
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,[self.alice.email])
        self.assertNotIn('Private logistics',mail.outbox[0].body)
        self.assertIn('ongoing opportunity you enrolled in',mail.outbox[0].body)
        self.alice.profile.activity_email_enabled=False;self.alice.profile.save()
        with self.captureOnCommitCallbacks(execute=True):cancel_activity(self.activity.pk,self.host,'Stopped')
        self.assertEqual(len(mail.outbox),1)
        event=ActivityNotificationEvent.objects.get(kind='cancellation')
        self.assertEqual(event.deliveries.get().reason,'recipient_opted_out')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_details_show_only_own_history_and_roster_preserves_decision_actor(self):
        alice=self.apply();bob=self.apply(self.bob);self.approve(alice)
        page=self.client.get(self.activity.get_absolute_url())
        self.assertEqual([r.user_id for r in page.context['enrollment_history']],[self.alice.pk])
        self.client.force_login(self.host)
        page=self.client.get(reverse('activities:roster',args=[self.activity.pk]))
        self.assertContains(page,'Admission: Approved by jan')
        self.assertContains(page,'Place: Secured')
        self.assertContains(page,'1 pending')
        before=list(AdmissionDecision.objects.values())
        self.client.get(reverse('activities:roster',args=[self.activity.pk]))
        self.assertEqual(list(AdmissionDecision.objects.values()),before)

    def test_pool_policy_and_capacity_are_immutable_and_admin_history_is_readonly(self):
        from .admin import NotificationAuditAdmin
        for name,value in [('capacity',2),('policy','eligibility_only'),('version',2)]:
            pool=OngoingOpportunity.objects.get(pk=self.pool.pk);setattr(pool,name,value)
            with self.assertRaises(ValidationError):pool.save()
        request=RequestFactory().get('/');request.user=self.host
        for model in [OngoingOpportunity,EnrollmentRequest,AdmissionDecision,OngoingEnrollment,CohortPlace]:
            admin=NotificationAuditAdmin(model,AdminSite())
            self.assertFalse(admin.has_add_permission(request));self.assertFalse(admin.has_change_permission(request));self.assertFalse(admin.has_delete_permission(request))
        a=self.apply()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EnrollmentRequest.objects.create(opportunity=self.pool,user=self.alice)


class EnrollmentMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_legacy_and_all_poll_evidence_without_enrollment_backfill(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes()
        old=[('activities','0025_alter_activitynotificationevent_kind_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            u=apps.get_model('auth','User').objects.create(username='d1-migration')
            a=apps.get_model('activities','Activity').objects.create(host_id=u.pk,title='Legacy',available_responses=['interested','vote'])
            apps.get_model('activities','ActivityResponse').objects.create(activity_id=a.pk,user_id=u.pk,status='interested',note='Keep')
            poll=apps.get_model('activities','DatePoll').objects.create(activity_id=a.pk)
            option=apps.get_model('activities','DatePollOption').objects.create(poll_id=poll.pk,position=1,starts_at=timezone.now())
            submission=apps.get_model('activities','DatePollSubmission').objects.create(poll_id=poll.pk,user_id=u.pk,answers={str(option.pk):'maybe'})
            round=apps.get_model('activities','ConfirmationRound').objects.create(poll_id=poll.pk,selected_option_id=option.pk,finalized_by_id=u.pk,prior_schedule={'freetext_when':'TBD'})
            apps.get_model('activities','ConfirmationInvitation').objects.create(round_id=round.pk,user_id=u.pk)
            apps.get_model('activities','AttendanceAnswer').objects.create(round_id=round.pk,user_id=u.pk,status='declined')
            event=apps.get_model('activities','ActivityNotificationEvent').objects.create(activity_id=a.pk,actor_id=u.pk,kind='confirmation',confirmation_round_id=round.pk)
            apps.get_model('activities','ActivityNotificationDelivery').objects.create(event_id=event.pk,recipient_id=u.pk,recipient_hash='0'*64,status='sent')
            names=['Activity','ActivityResponse','DatePoll','DatePollOption','DatePollSubmission','ConfirmationRound','ConfirmationInvitation','AttendanceAnswer','ActivityNotificationEvent','ActivityNotificationDelivery']
            snapshots={name:list(apps.get_model('activities',name).objects.values()) for name in names}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as current
            for name,rows in snapshots.items():self.assertEqual(list(current.get_model('activities',name).objects.values(*rows[0].keys())),rows,name)
            self.assertIsNone(Activity.objects.get(pk=a.pk).ongoing_opportunity_id)
            self.assertFalse(OngoingOpportunity.objects.exists());self.assertFalse(EnrollmentRequest.objects.exists())
        finally:MigrationExecutor(connection).migrate(leaves)


class EnrollmentConcurrencyTests(SimpleTestCase):
    def test_file_backed_last_player_approval_withdrawal_and_cancellation_races(self):
        with tempfile.TemporaryDirectory() as root:
            env=os.environ.copy();env.update(BELONG_ENV='test',DJANGO_DB_PATH=str(Path(root)/'race.sqlite3'),EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
            script=r'''
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','belong.settings');django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.management import call_command
from django.db import close_old_connections
from activities.models import *
from activities.enrollment import request_place, decide_request, withdraw_request
from activities.participation import cancel_activity
from activities.participation_config import make_config
from belong.test_helpers import create_legacy_user
call_command('migrate',verbosity=0)
u=[create_legacy_user('d1-race-'+str(n)) for n in range(5)]
def fixture():
 a=Activity.objects.create(host=u[0],title='D1 race',cost_type='free',participation_config=make_config('ongoing',version=4))
 p=OngoingOpportunity.objects.create(activity=a,capacity=1)
 for user in u[1:]:request_place(a.pk,user)
 return a,p,list(p.requests.all())
def parallel(actions):
 barrier=Barrier(len(actions))
 def run(f):
  close_old_connections()
  try:barrier.wait(timeout=10);f()
  finally:close_old_connections()
 with ThreadPoolExecutor(max_workers=len(actions)) as pool:list(pool.map(run,actions))
for attempt in range(3):
 a,p,rows=fixture()
 parallel([lambda:request_place(a.pk,u[1]),lambda:request_place(a.pk,u[1])])
 assert p.requests.filter(user=u[1]).count()==1
 parallel([lambda row=row:decide_request(a.pk,u[0],row.pk,'approved') for row in rows])
 assert AdmissionDecision.objects.filter(request__opportunity=p,result='approved').count()==1
 assert OngoingEnrollment.objects.filter(request__opportunity=p,ended_at__isnull=True).count()==1
 assert CohortPlace.objects.filter(enrollment__request__opportunity=p,released_at__isnull=True).count()==1
 assert p.requests.filter(decision__isnull=True,closed_at__isnull=True).count()==3
 a,p,rows=fixture()
 parallel([lambda:decide_request(a.pk,u[0],rows[0].pk,'approved'),lambda:withdraw_request(a.pk,u[1],rows[0].pk)])
 assert CohortPlace.objects.filter(enrollment__request__opportunity=p,released_at__isnull=True).count()==0
 assert OngoingEnrollment.objects.filter(request__opportunity=p,ended_at__isnull=True).count()==0
 assert p.requests.get(pk=rows[0].pk).withdrawn_at
 a,p,rows=fixture()
 parallel([lambda:decide_request(a.pk,u[0],rows[0].pk,'approved'),lambda:cancel_activity(a.pk,u[0],'Stop')])
 a.refresh_from_db();assert a.is_cancelled
 decision=AdmissionDecision.objects.filter(request=rows[0]).first()
 assert decision is None or decision.created_at <= a.cancelled_at
 decide_request(a.pk,u[0],rows[1].pk,'approved')
 assert AdmissionDecision.objects.filter(request__opportunity=p).count()<=1
 assert ActivityResponse.objects.filter(activity=a).count()==0
print('D1 races passed')
'''
            result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('D1 races passed',result.stdout)
