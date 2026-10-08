"""D3 free-only policy, durable expiry/FIFO, privacy and capacity serialization."""
from datetime import timedelta
from io import StringIO
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404
from django.test import TestCase, SimpleTestCase, TransactionTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from social.models import Friendship
from .models import (Activity, ActivityInvitation, ActivityResponse, RegistrationTarget,
    RegistrationRequest, RegistrationAdmission, FreeRegistration, RegistrationPlace,
    FreeReservationPool, FreeReservationHold, FreeWaitlistEntry, FreePoolCapacityChange,
    ActivityNotificationEvent, OngoingOpportunity)
from .forms import ActivityForm
from .participation_config import make_config
from .registration import mutate as register, registrations_for
from .reservations import mutate, resize, used, live_holds
from .participation import cancel_activity
from .polls import recipient_ids
from .notifications import deliver_one
from belong.email_controls import address_hash


class FreeReservationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host=create_legacy_user('d3-host')
        cls.alice=create_legacy_user('d3-alice')
        cls.bob=create_legacy_user('d3-bob')
        cls.carol=create_legacy_user('d3-carol')

    def setUp(self):
        self.activity=Activity.objects.create(host=self.host,title='D3 free workshop',cost_type='free',participation_config=make_config('registration',version=5))
        self.target=RegistrationTarget.objects.create(activity=self.activity,amount=0,admission='open',allocation='claim',capacity=1)
        self.pool=FreeReservationPool.objects.create(target=self.target,capacity=1,waitlist_enabled=True)
        self.rows={}
        for user in [self.alice,self.bob,self.carol]:
            register(self.activity.pk,user,'submit',version='1')
            self.rows[user.pk]=self.target.requests.get(user=user)
        self.client.force_login(self.alice)

    def act(self, action, user=None, **kwargs):
        user=user or self.alice
        defaults=dict(policy='1',revision=str(self.pool.revision),request_id=self.rows[user.pk].pk)
        defaults.update(kwargs)
        return mutate(self.activity.pk,user,action,**defaults)

    def hold(self,user=None,**kwargs):
        user=user or self.alice
        self.act('hold',user,**kwargs)
        return self.pool.holds.filter(user=user).last()

    def queue(self,user,**kwargs):
        self.act('join_queue',user,**kwargs)
        return self.pool.entries.filter(user=user).last()

    def test_creator_policy_is_explicit_free_limited_and_never_backfills_d2(self):
        data=dict(title='New D3 class',description='Details',cost_type='free',location_type='tbd',audience='everyone',participation_pattern='registration',registration_allocation='claim',registration_admission='open',capacity='2',registration_reservations='on',registration_waitlist='on')
        self.client.force_login(self.host)
        response=self.client.post(reverse('activities:create'),data)
        a=Activity.objects.latest('pk');self.assertRedirects(response,a.get_absolute_url())
        self.assertEqual(a.registration_target.reservation_pool.capacity,2)
        self.assertTrue(a.registration_target.reservation_pool.waitlist_enabled)
        for change in [dict(cost_type='paid',cost_amount='10'),dict(capacity=''),dict(registration_allocation='approval',registration_admission='request'),dict(registration_reservations='')]:
            self.assertFalse(ActivityForm({**data,**change},user=self.host).is_valid(),change)
        old=Activity.objects.create(host=self.host,title='D2',cost_type='free',participation_config=make_config('registration',version=5))
        target=RegistrationTarget.objects.create(activity=old,amount=0,admission='open',allocation='claim',capacity=1)
        register(old.pk,self.alice,'submit',version='1')
        with self.assertRaises(ValidationError):FreeReservationPool.objects.create(target=target,capacity=1)
        self.assertFalse(FreeReservationPool.objects.filter(target=target).exists())

    def test_hold_is_not_confirmation_and_retries_reads_never_renew_deadline(self):
        hold=self.hold();deadline=hold.expires_at
        self.assertAlmostEqual((hold.expires_at-hold.created_at).total_seconds(),600,delta=1)
        with self.assertRaises(IntegrityError),transaction.atomic():
            FreeReservationHold.objects.create(pool=self.pool,request=self.rows[self.alice.pk],user=self.alice,expires_at=timezone.now()+timedelta(minutes=10))
        self.assertEqual(used(self.pool),1)
        self.act('hold');self.act('refresh')
        for path in [self.activity.get_absolute_url(),'/?q=D3',reverse('activities:roster',args=[self.activity.pk])]:self.client.get(path)
        hold.refresh_from_db();self.assertEqual(hold.expires_at,deadline);self.assertEqual(self.pool.holds.count(),1)
        self.assertFalse(FreeRegistration.objects.exists());self.assertFalse(RegistrationPlace.objects.exists());self.assertFalse(ActivityResponse.objects.exists())
        self.assertEqual(recipient_ids(self.activity),set())
        self.assertContains(self.client.get(self.activity.get_absolute_url()),'You are not registered yet')
        self.assertContains(self.client.get('/?q=D3'),'Place held / View')

    def test_d2_claim_cannot_bypass_hold_and_explicit_accept_replaces_own_capacity_once(self):
        row=self.rows[self.alice.pk]
        register(self.activity.pk,self.alice,'claim',version='1',request_id=row.pk)
        self.assertFalse(FreeRegistration.objects.exists())
        hold=self.hold();self.act('accept',hold_id=hold.pk);self.act('accept',hold_id=hold.pk)
        hold.refresh_from_db();self.assertEqual(hold.end_reason,'accepted')
        self.assertEqual(used(self.pool),1);self.assertEqual(FreeRegistration.objects.count(),1);self.assertEqual(RegistrationPlace.objects.count(),1)
        self.assertEqual(recipient_ids(self.activity),{self.alice.pk})
        self.assertIn('already ended', self.act('release',hold_id=hold.pk))
        self.assertEqual(used(self.pool),1)
        self.assertIn('Full',self.act('hold',self.bob))
        self.assertFalse(self.pool.entries.exists())

    def test_expiry_equality_reclaims_without_worker_and_stale_retry_cannot_reacquire(self):
        hold=self.hold()
        with patch('activities.reservations.timezone.now',return_value=hold.expires_at):
            self.assertFalse(live_holds(self.pool).exists())
            self.assertIn('ended',self.act('accept',hold_id=hold.pk))
            self.assertIn('Reload',self.act('hold'))
            other=self.hold(self.bob)
            self.assertIsNotNone(other)
        hold.refresh_from_db();self.assertEqual(hold.end_reason,'expired')
        self.assertFalse(FreeRegistration.objects.exists());self.assertEqual(self.pool.holds.count(),2)

    def test_fifo_explicit_optin_promotion_and_duplicate_cleanup_are_idempotent(self):
        hold=self.hold()
        self.assertIn('Full',self.act('hold',self.bob));self.assertFalse(self.pool.entries.exists())
        bob=self.queue(self.bob);carol=self.queue(self.carol)
        self.act('join_queue',self.bob)
        self.assertEqual(self.pool.entries.count(),2)
        self.act('release',hold_id=hold.pk)
        bob.refresh_from_db();offer=bob.offer
        self.assertAlmostEqual((offer.expires_at-offer.created_at).total_seconds(),86400,delta=1)
        self.assertFalse(hasattr(carol,'offer'));self.assertEqual(used(self.pool),1)
        self.act('refresh',self.bob);call_command('expire_reservations',stdout=StringIO());call_command('expire_reservations',stdout=StringIO())
        self.assertEqual(self.pool.holds.filter(entry=bob).count(),1)
        self.assertEqual(ActivityNotificationEvent.objects.filter(reservation_hold=offer).count(),1)
        self.assertFalse(FreeRegistration.objects.exists())
        self.assertEqual(recipient_ids(self.activity),set())
        self.act('accept',self.bob,hold_id=offer.pk)
        self.assertEqual(registrations_for(self.activity).count(),1)
        self.assertEqual(used(self.pool),1)

    def test_expired_offer_promotes_next_and_requires_explicit_rejoin_at_tail(self):
        hold=self.hold();bob=self.queue(self.bob);carol=self.queue(self.carol)
        self.act('release',hold_id=hold.pk);offer=bob.offer
        with patch('activities.reservations.timezone.now',return_value=offer.expires_at):
            self.assertIn('ended',self.act('accept',self.bob,hold_id=offer.pk))
            bob.refresh_from_db();self.assertEqual(bob.end_reason,'expired')
            carol.refresh_from_db();self.assertTrue(hasattr(carol,'offer'))
            self.act('join_queue',self.bob)
            self.assertEqual(self.pool.entries.filter(user=self.bob).count(),1)
            again=self.queue(self.bob,entry_id=bob.pk)
            self.assertGreater(again.pk,carol.pk)
            self.act('leave_queue',self.bob,entry_id=bob.pk)
            again.refresh_from_db();self.assertIsNone(again.ended_at)
        self.assertFalse(FreeRegistration.objects.exists())

    def test_offer_decline_queue_withdraw_and_registration_withdraw_promote_without_attendance(self):
        hold=self.hold();bob=self.queue(self.bob);carol=self.queue(self.carol)
        self.act('release',hold_id=hold.pk)
        self.act('release',self.bob,hold_id=bob.offer.pk)
        bob.refresh_from_db();self.assertEqual(bob.end_reason,'declined')
        self.assertTrue(hasattr(self.pool.entries.get(pk=carol.pk),'offer'))
        self.act('leave_queue',self.carol,entry_id=carol.pk)
        carol.refresh_from_db();self.assertEqual(carol.end_reason,'withdrawn');self.assertEqual(used(self.pool),0)
        hold=self.hold(hold_id=hold.pk);self.act('accept',hold_id=hold.pk)
        bob2=self.queue(self.bob,entry_id=bob.pk)
        register(self.activity.pk,self.alice,'withdraw',version='1',request_id=self.rows[self.alice.pk].pk)
        self.assertTrue(hasattr(self.pool.entries.get(pk=bob2.pk),'offer'))
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertEqual(RegistrationPlace.objects.filter(released_at__isnull=True).count(),0)

    def test_pending_approval_cannot_hold_or_queue_and_denial_retains_history(self):
        a=Activity.objects.create(host=self.host,title='Approval',cost_type='free',participation_config=make_config('registration',version=5))
        t=RegistrationTarget.objects.create(activity=a,amount=0,admission='request',allocation='claim',capacity=1)
        pool=FreeReservationPool.objects.create(target=t,capacity=1,waitlist_enabled=True)
        register(a.pk,self.bob,'submit',version='1');row=t.requests.get()
        for action in ['hold','join_queue']:
            self.assertIn('not currently satisfied',mutate(a.pk,self.bob,action,policy='1',revision='1',request_id=row.pk))
        register(a.pk,self.host,'decide',version='1',request_id=row.pk,decision='denied')
        self.assertFalse(pool.holds.exists());self.assertFalse(pool.entries.exists())
        self.assertTrue(RegistrationAdmission.objects.filter(request=row,result='denied').exists())

    def test_invitation_loss_before_accept_closes_hold_and_queue_not_secured_entitlement(self):
        a=Activity.objects.create(host=self.host,title='Invited',cost_type='free',participation_config=make_config('registration',version=5))
        t=RegistrationTarget.objects.create(activity=a,amount=0,admission='invitation',allocation='claim',capacity=1)
        pool=FreeReservationPool.objects.create(target=t,capacity=1,waitlist_enabled=True)
        invitation=ActivityInvitation.objects.create(activity=a,user=self.alice,invited_by=self.host)
        register(a.pk,self.alice,'submit',version='1');row=t.requests.get()
        mutate(a.pk,self.alice,'hold',policy='1',revision='1',request_id=row.pk);hold=pool.holds.get();invitation.delete()
        mutate(a.pk,self.alice,'accept',policy='1',revision='1',request_id=row.pk,hold_id=hold.pk)
        hold.refresh_from_db();self.assertEqual(hold.end_reason,'ineligible');self.assertFalse(FreeRegistration.objects.exists())
        ActivityInvitation.objects.create(activity=a,user=self.alice,invited_by=self.host)
        mutate(a.pk,self.alice,'hold',policy='1',revision='1',request_id=row.pk,hold_id=hold.pk);second=pool.holds.last()
        mutate(a.pk,self.alice,'accept',policy='1',revision='1',request_id=row.pk,hold_id=second.pk)
        a.direct_invitations.all().delete();call_command('expire_reservations',stdout=StringIO())
        self.assertEqual(registrations_for(a).count(),1)

    def test_capacity_management_version_bounds_and_immutable_quote(self):
        hold=self.hold();deadline=hold.expires_at
        self.assertIn('positive',resize(self.activity.pk,self.host,0,policy='1',revision='1'))
        resize(self.activity.pk,self.host,2,policy='1',revision='1');self.pool.refresh_from_db()
        self.assertEqual(self.pool.revision,2);self.assertEqual(self.target.capacity,1)
        bob=self.hold(self.bob)
        self.assertIn('cannot be reduced',resize(self.activity.pk,self.host,1,policy='1',revision='2'))
        self.assertIn('Reload',self.act('accept',hold_id=hold.pk,revision='1'))
        hold.refresh_from_db();self.assertEqual(hold.expires_at,deadline)
        self.act('accept',hold_id=hold.pk)
        self.act('release',self.bob,hold_id=bob.pk)
        resize(self.activity.pk,self.host,1,policy='1',revision='2');self.pool.refresh_from_db()
        self.assertEqual(self.pool.capacity,1);self.assertEqual(FreePoolCapacityChange.objects.count(),2)
        with self.assertRaises(Http404):resize(self.activity.pk,self.bob,2,policy='1',revision='3')
        with self.assertRaises(ValidationError):self.pool.capacity=2;self.pool.save()

    def test_hold_deadline_and_identity_cannot_be_edited_and_closed_request_cannot_touch_reapplication(self):
        hold=self.hold()
        hold.expires_at+=timedelta(minutes=1)
        with self.assertRaises(ValidationError):hold.save()
        old=self.rows[self.alice.pk]
        register(self.activity.pk,self.alice,'withdraw',version='1',request_id=old.pk)
        register(self.activity.pk,self.alice,'submit',version='1',request_id=old.pk)
        new=self.target.requests.filter(user=self.alice).last()
        mutate(self.activity.pk,self.alice,'hold',policy='1',revision='1',request_id=new.pk,hold_id=hold.pk)
        newer=self.pool.holds.last()
        self.act('release',hold_id=hold.pk)
        newer.refresh_from_db();self.assertIsNone(newer.ended_at)

    def test_cancel_ends_holds_queue_without_promotion_or_erasing_secured_places(self):
        hold=self.hold();bob=self.queue(self.bob);self.queue(self.carol)
        cancel_activity(self.activity.pk,self.host,'Stopped')
        hold.refresh_from_db();bob.refresh_from_db()
        self.assertEqual(hold.end_reason,'cancelled');self.assertEqual(bob.end_reason,'cancelled')
        before=self.pool.holds.count();call_command('expire_reservations',stdout=StringIO())
        self.assertEqual(self.pool.holds.count(),before);self.assertEqual(used(self.pool),0)
        self.assertIn('Cancelled',self.act('accept',hold_id=hold.pk));self.assertFalse(FreeRegistration.objects.exists())
        self.assertContains(self.client.get(self.activity.get_absolute_url()),'Cancelled')

    def test_gets_derive_expiry_without_writes_and_optional_sweeper_records_it(self):
        hold=self.hold();deadline=hold.expires_at
        with patch('activities.reservations.timezone.now',return_value=deadline):
            before=list(self.pool.holds.values())
            self.assertContains(self.client.get(self.activity.get_absolute_url()),'has expired')
            self.assertContains(self.client.get('/?q=D3'),'Hold expired / View')
            self.assertEqual(list(self.pool.holds.values()),before)
            call_command('expire_reservations',stdout=StringIO());call_command('expire_reservations',stdout=StringIO())
        hold.refresh_from_db();self.assertEqual(hold.end_reason,'expired');self.assertEqual(hold.expires_at,deadline)

    def test_action_scope_auth_csrf_policy_and_foreign_hold(self):
        hold=self.hold()
        for action in ['accept','release']:
            with self.assertRaises(Http404):self.act(action,self.bob,hold_id=hold.pk)
        self.act('release',hold_id=hold.pk,revision='999');hold.refresh_from_db();self.assertIsNone(hold.ended_at)
        route=reverse('activities:reservation_action',args=[self.activity.pk,'hold'])
        self.assertEqual(self.client.get(route).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.alice)
        self.assertEqual(csrf.post(route,{}).status_code,403)
        self.assertEqual(self.client.post(reverse('activities:reservation_action',args=[self.activity.pk,'pay']),{}).status_code,404)
        self.activity.audience='friends';self.activity.save()
        with self.assertRaises(Http404):self.act('release',hold_id=hold.pk)

    def test_htmx_native_safe_filters_private_history_and_roster_deadlines(self):
        path='/?q=D3&audience=everyone&audience=friends&cost=free'
        route=reverse('activities:reservation_action',args=[self.activity.pk,'hold'])
        data=dict(policy='1',pool_revision='1',request=self.rows[self.alice.pk].pk,variant='detail',next=path)
        page=self.client.post(route,data,HTTP_HX_REQUEST='true')
        self.assertContains(page,'Place held until');self.assertContains(page,'Confirm free registration')
        self.assertContains(page,'name="next" value="/?q=D3&amp;audience=everyone&amp;audience=friends&amp;cost=free"')
        hold=self.pool.holds.get();self.queue(self.bob)
        page=self.client.get(self.activity.get_absolute_url());self.assertEqual(len(page.context['reservation_history']),1);self.assertEqual(list(page.context['reservation_entries']),[])
        response=self.client.post(reverse('activities:reservation_action',args=[self.activity.pk,'release']),{**data,'hold':hold.pk})
        self.assertEqual(response.url,path)
        self.client.force_login(self.host)
        page=self.client.get(reverse('activities:roster',args=[self.activity.pk]));self.assertContains(page,'Offered');self.assertContains(page,'Update free place limit');self.assertEqual(len(page.context['reservation_history']),2)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BELONG_PUBLIC_ORIGIN='https://belong.example')
    def test_durable_offer_notice_reuses_verified_optin_and_is_not_update_subscription(self):
        for user in [self.host,self.bob]:
            user.email=user.username+'@example.invalid';user.save()
            user.profile.email_verified_at=timezone.now();user.profile.activity_email_enabled=True;user.profile.save()
        hold=self.hold();entry=self.queue(self.bob)
        with self.captureOnCommitCallbacks(execute=True):self.act('release',hold_id=hold.pk)
        offer=self.pool.entries.get(pk=entry.pk).offer
        event=ActivityNotificationEvent.objects.get(reservation_hold=offer)
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,[self.bob.email])
        self.assertIn('not registered yet',mail.outbox[0].body);self.assertNotIn(self.activity.title,mail.outbox[0].body)
        self.assertEqual(recipient_ids(self.activity),set())
        call_command('expire_reservations',stdout=StringIO());self.assertEqual(len(mail.outbox),1)
        self.assertEqual(event.deliveries.get().status,'sent')
        self.carol.email='d3-carol@example.invalid';self.carol.save()
        self.carol.profile.email_verified_at=timezone.now();self.carol.profile.activity_email_enabled=True;self.carol.profile.save()
        self.queue(self.carol)
        with patch('belong.email_controls.send_mail',side_effect=RuntimeError('transport failure')):
            with self.captureOnCommitCallbacks(execute=True):self.act('release',self.bob,hold_id=offer.pk)
        next_offer=self.pool.holds.filter(user=self.carol).get()
        next_event=ActivityNotificationEvent.objects.get(reservation_hold=next_offer)
        self.assertEqual(next_event.deliveries.get().status,'failed')
        self.assertIsNone(next_offer.ended_at);self.assertEqual(used(self.pool),1)
        deadline=next_offer.expires_at
        self.act('accept',self.carol,hold_id=next_offer.pk)
        next_offer.refresh_from_db();self.assertEqual(next_offer.expires_at,deadline)
        self.assertEqual(next_offer.end_reason,'accepted');self.assertEqual(used(self.pool),1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',BELONG_PUBLIC_ORIGIN='https://belong.example')
    def test_optout_and_late_delivery_do_not_extend_or_roll_back_offer(self):
        for user in [self.host,self.bob]:
            user.email=user.username+'@example.invalid';user.save()
            user.profile.email_verified_at=timezone.now();user.profile.activity_email_enabled=False;user.profile.save()
        hold=self.hold();entry=self.queue(self.bob)
        self.act('release',hold_id=hold.pk)
        offer=self.pool.entries.get(pk=entry.pk).offer;event=ActivityNotificationEvent.objects.get(reservation_hold=offer)
        self.assertEqual(event.deliveries.get().status,'skipped');self.assertEqual(event.deliveries.get().reason,'recipient_opted_out')
        for user in [self.host,self.bob]:
            user.email=user.username+'@example.invalid';user.save()
            user.profile.email_verified_at=timezone.now();user.profile.activity_email_enabled=True;user.profile.save()
        # Re-enable a pending transport only for exercising its dispatch guard.
        delivery=event.deliveries.get();delivery.status='pending';delivery.recipient_hash=address_hash(self.bob.email);delivery.save()
        with patch('activities.notifications.timezone.now',return_value=offer.expires_at):
            deliver_one(delivery.pk)
        delivery.refresh_from_db();self.assertEqual(delivery.reason,'offer_ended');self.assertEqual(len(mail.outbox),0)
        offer.refresh_from_db();self.assertIsNone(offer.ended_at)


class ReservationMigrationTests(TransactionTestCase):
    def test_migration_is_additive_and_never_converts_existing_d2_quotes_or_confirmations(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes();old=[('activities','0027_freeregistration_registrationplace_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            u=apps.get_model('auth','User').objects.create(username='d3-migration')
            a=apps.get_model('activities','Activity').objects.create(host_id=u.pk,title='D2',participation_config=make_config('registration',version=5))
            t=apps.get_model('activities','RegistrationTarget').objects.create(activity_id=a.pk,admission='open',allocation='claim',capacity=1,amount=0)
            r=apps.get_model('activities','RegistrationRequest').objects.create(target_id=t.pk,user_id=u.pk)
            c=apps.get_model('activities','FreeRegistration').objects.create(request_id=r.pk)
            apps.get_model('activities','RegistrationPlace').objects.create(confirmation_id=c.pk)
            names=['Activity','RegistrationTarget','RegistrationRequest','FreeRegistration','RegistrationPlace']
            before={name:list(apps.get_model('activities',name).objects.values()) for name in names}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as current
            for name,rows in before.items():self.assertEqual(list(current.get_model('activities',name).objects.values()),rows,name)
            self.assertFalse(FreeReservationPool.objects.exists());self.assertFalse(FreeReservationHold.objects.exists());self.assertFalse(FreeWaitlistEntry.objects.exists())
        finally:MigrationExecutor(connection).migrate(leaves)


class FreeReservationRaceTests(SimpleTestCase):
    def test_file_backed_last_hold_expire_accept_promotion_capacity_and_cancellation_races(self):
        script=r'''
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','belong.settings');django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from belong.test_helpers import create_legacy_user
from activities.models import *
from activities.participation_config import make_config
from activities.registration import mutate as register,registrations_for
from activities.reservations import mutate,used,resize
from activities.participation import cancel_activity
call_command('migrate',verbosity=0)
u=[create_legacy_user('d3-race-'+str(n)) for n in range(5)]
def parallel(actions):
 barrier=Barrier(len(actions))
 def run(action):
  close_old_connections()
  try:barrier.wait(timeout=10);action()
  finally:close_old_connections()
 with ThreadPoolExecutor(max_workers=len(actions)) as pool:list(pool.map(run,actions))
def fixture(capacity=1):
 a=Activity.objects.create(host=u[0],title='Race',cost_type='free',participation_config=make_config('registration',version=5))
 t=RegistrationTarget.objects.create(activity=a,admission='open',allocation='claim',amount=0,capacity=capacity)
 p=FreeReservationPool.objects.create(target=t,capacity=capacity,waitlist_enabled=True)
 for user in u[1:]:register(a.pk,user,'submit',version='1')
 rows={r.user_id:r for r in t.requests.all()}
 def act(action,user=u[1],**kw):return mutate(a.pk,user,action,policy='1',revision='1',request_id=rows[user.pk].pk,**kw)
 return a,t,p,rows,act
for attempt in range(3):
 a,t,p,rows,act=fixture()
 parallel([lambda user=user:act('hold',user) for user in u[1:]])
 assert p.holds.filter(ended_at__isnull=True).count()==1 and used(p)==1
 h=p.holds.get();parallel([lambda:act('accept',h.user,hold_id=h.pk),lambda:act('accept',h.user,hold_id=h.pk)])
 assert registrations_for(a).count()==1 and used(p)==1
 a,t,p,rows,act=fixture()
 act('hold');h=p.holds.get()
 # Persist a short valid lifetime, then race cleanup/accept at expiry.
 FreeReservationHold.objects.filter(pk=h.pk).update(expires_at=h.created_at+timedelta(milliseconds=20))
 parallel([lambda:act('accept',hold_id=h.pk),lambda:act('hold',u[2])])
 assert used(p)<=1 and registrations_for(a).count()<=1
 a,t,p,rows,act=fixture()
 act('hold');h=p.holds.get();act('join_queue',u[2]);act('join_queue',u[3])
 parallel([lambda:act('release',hold_id=h.pk),lambda:act('release',hold_id=h.pk),lambda:act('refresh',u[2])])
 assert p.holds.filter(entry__isnull=False).count()==1 and used(p)==1
 offer=p.holds.get(entry__isnull=False)
 assert offer.user_id==u[2].pk
 parallel([lambda:act('accept',u[2],hold_id=offer.pk),lambda:act('release',u[2],hold_id=offer.pk)])
 assert used(p)<=1 and registrations_for(a).count()<=1
 assert ActivityNotificationEvent.objects.filter(reservation_hold__pool=p).count()<=2
 a,t,p,rows,act=fixture()
 act('hold');h=p.holds.get();act('join_queue',u[2]);act('join_queue',u[3]);act('release',hold_id=h.pk)
 offer=p.holds.get(entry__isnull=False)
 with patch('activities.reservations.timezone.now',return_value=offer.expires_at):
  parallel([lambda:act('accept',u[2],hold_id=offer.pk),lambda:act('refresh',u[3])])
 assert registrations_for(a).count()==0 and used(p)<=1
 offer.refresh_from_db();assert offer.end_reason=='expired'
 assert p.holds.filter(entry__isnull=False,user=u[3]).count()==1
 a,t,p,rows,act=fixture(2)
 act('hold')
 parallel([lambda:resize(a.pk,u[0],1,policy='1',revision='1'),lambda:act('hold',u[2])])
 p.refresh_from_db();assert used(p)<=p.capacity
 a,t,p,rows,act=fixture()
 act('hold');h=p.holds.get();act('join_queue',u[2])
 parallel([lambda:act('accept',hold_id=h.pk),lambda:cancel_activity(a.pk,u[0],'Stop')])
 a.refresh_from_db();assert a.is_cancelled
 assert p.holds.filter(ended_at__isnull=True).count()==0
 c=FreeRegistration.objects.filter(request__target=t).first()
 assert c is None or c.created_at<=a.cancelled_at
 assert used(p)<=1 and ActivityResponse.objects.count()==0
print('D3 races passed')
'''
        with tempfile.TemporaryDirectory() as root:
            env=os.environ.copy();env.update(BELONG_ENV='test',DJANGO_DB_PATH=str(Path(root)/'race.sqlite3'),EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
            result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('D3 races passed',result.stdout)
