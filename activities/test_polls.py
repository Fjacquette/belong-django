"""Bobby: availability is not attendance, and finalization preserves evidence."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from social.models import Friendship, OutboundEmailAttempt
from .models import (Activity, ActivityResponse, ActivityInvitation, DatePoll, DatePollOption,
    DatePollSubmission, ConfirmationRound, ConfirmationInvitation, AttendanceAnswer,
    ActivityNotificationEvent, ActivityNotificationDelivery, Announcement)
from .forms import ActivityForm, ActivitySeriesForm
from .polls import create_poll, finalize_poll, submit_answers, responses_for, recipient_ids
from .participation_config import make_config
from .participation import cancel_activity
from .notifications import deliver_event, deliver_one, queue_event
from .announcements import updates_for
from .group_offers import current_offer


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
class DatePollTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host=cls.person('bobby'); cls.alice=cls.person('alice'); cls.bob=cls.person('bob'); cls.other=cls.person('viewer')

    @staticmethod
    def person(name):
        u=create_legacy_user(name,email=name+'@example.invalid')
        u.profile.email_verified_at=timezone.now();u.profile.activity_email_enabled=True;u.profile.save()
        return u

    def setUp(self):
        self.client.force_login(self.alice)
        self.activity=Activity.objects.create(host=self.host,title='Tentative Hersheypark',description='Private planning details',
            cost_type='free',capacity=1,participation_config=make_config('planning',version=3))
        self.dates=[timezone.now()+timezone.timedelta(days=n) for n in (10,11,12)]
        self.poll=create_poll(self.activity,self.dates)
        self.options=list(self.poll.options.all())

    def answers(self, values=('yes','maybe','no')):
        return {f'option_{o.pk}':v for o,v in zip(self.options,values)}

    def vote(self,user=None,values=('yes','maybe','no'),**kwargs):
        if user:self.client.force_login(user)
        return self.client.post(reverse('activities:poll_vote',args=[self.activity.pk]),
            {**self.answers(values),'variant':'detail',**kwargs},HTTP_HX_REQUEST='true')

    def finalize(self):
        finalize_poll(self.activity.pk,self.host,self.options[1].pk)
        return ConfirmationRound.objects.get(poll=self.poll)

    def respond(self,action='confirm_attendance',round=None,user=None,**kwargs):
        if user:self.client.force_login(user)
        round=round or ConfirmationRound.objects.get(poll=self.poll)
        return self.client.post(reverse('activities:respond',args=[self.activity.pk]),
            {'action':action,'confirmation_round':round.pk,'variant':'detail',**kwargs},HTTP_HX_REQUEST='true')

    def test_creator_publishes_three_future_options_and_no_response_or_membership(self):
        self.client.force_login(self.host)
        data={'title':'New tentative plan','description':'Choose a date','participation_pattern':'planning','cost_type':'free',
              'location_type':'tbd','audience':'everyone',**{f'poll_date_{n}':d.strftime('%Y-%m-%dT%H:%M') for n,d in enumerate(self.dates,1)}}
        response=self.client.post(reverse('activities:create'),data)
        a=Activity.objects.latest('pk');self.assertRedirects(response,a.get_absolute_url())
        self.assertEqual(a.participation_config,make_config('planning',version=3))
        self.assertEqual(a.available_responses,[]);self.assertIsNone(a.starts_at)
        self.assertEqual(a.date_poll.options.count(),3)
        self.assertFalse(ActivityResponse.objects.exists());self.assertFalse(GroupMembership.objects.exists())
        for change in [{'poll_date_1':''},{'poll_date_2':data['poll_date_1']},{'cost_type':'paid','cost_amount':'20'},
                       {'poll_date_1':'2000-01-01T09:00'},{'starts_at':data['poll_date_1']}]:
            form=ActivityForm({**data,**change},user=self.host)
            self.assertFalse(form.is_valid(),change)
        self.assertNotIn('planning',dict(ActivitySeriesForm(user=self.host).fields['participation_pattern'].choices))

    def test_get_and_invitation_are_poll_navigation_never_synthetic_responses(self):
        ActivityInvitation.objects.create(activity=self.activity,user=self.alice,invited_by=self.host)
        for _ in range(2):
            self.assertContains(self.client.get('/?q=Tentative'),'Answer poll')
            detail=self.client.get(self.activity.get_absolute_url())
            self.assertContains(detail,'Which date works for you?')
            self.assertContains(detail,'Answer the date poll')
            self.assertNotContains(detail,'name="status"');self.assertNotContains(detail,'confirm_attendance')
        self.assertFalse(ActivityResponse.objects.exists());self.assertFalse(AttendanceAnswer.objects.exists())
        self.assertFalse(DatePollSubmission.objects.exists())
        self.client.post(reverse('activities:join',args=[self.activity.pk]))
        self.client.post(reverse('activities:respond',args=[self.activity.pk]),{'status':'vote','action':'confirm_attendance'})
        self.assertFalse(ActivityResponse.objects.exists());self.assertFalse(AttendanceAnswer.objects.exists())

    def test_edit_append_only_availability_and_idempotent_same_submission(self):
        self.vote();first=DatePollSubmission.objects.values().get()
        page=self.vote(values=('no','no','no'))
        self.assertContains(page,'Save availability changes')
        self.vote(values=('no','no','no'))
        self.assertEqual(DatePollSubmission.objects.count(),2)
        self.assertEqual(DatePollSubmission.objects.values().get(pk=first['id']),first)
        self.assertContains(self.client.get('/?q=Tentative'),'Poll answered / Edit answers')
        self.assertEqual(recipient_ids(self.activity),set());self.assertEqual(responses_for(self.activity),[])
        self.assertFalse(ActivityResponse.objects.exists());self.assertFalse(GroupMembership.objects.exists())
        self.assertIsNone(current_offer(self.alice))

    def test_invalid_incomplete_foreign_answers_and_wrong_methods_do_not_write(self):
        url=reverse('activities:poll_vote',args=[self.activity.pk])
        for data in [{}, {'option_99999':'yes'}, {**self.answers(),'option_'+str(self.options[0].pk):'committed'},
                     {k:v for k,v in self.answers().items() if not k.endswith(str(self.options[0].pk))}]:
            self.client.post(url,data)
        self.assertFalse(DatePollSubmission.objects.exists())
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.get(reverse('activities:poll_finalize',args=[self.activity.pk])).status_code,405)
        with self.assertRaises(ValidationError):make_config('planning',version=3,actions=['view_details','answer_poll','confirm_attendance'])

    def test_finalization_preserves_same_activity_all_options_answers_and_prior_response(self):
        self.vote();self.vote(self.bob,('no','no','no'))
        ActivityInvitation.objects.create(activity=self.activity,user=self.alice,invited_by=self.host)
        prior=ActivityResponse.objects.create(activity=self.activity,user=self.alice,status='question',note='Keep original question evidence')
        snapshot=ActivityResponse.objects.values().get(pk=prior.pk)
        options=list(DatePollOption.objects.values());submissions=list(DatePollSubmission.objects.values())
        round=self.finalize();self.activity.refresh_from_db()
        self.assertEqual(round.poll.activity_id,self.activity.pk)
        self.assertEqual(self.activity.starts_at,self.options[1].starts_at)
        self.assertEqual(self.activity.participation_config,make_config('planning',version=3))
        self.assertEqual(list(DatePollOption.objects.values()),options)
        self.assertEqual(list(DatePollSubmission.objects.values()),submissions)
        self.assertEqual(ActivityResponse.objects.values().get(pk=prior.pk),snapshot)
        self.assertEqual(set(round.invitations.values_list('user_id',flat=True)),{self.alice.pk,self.bob.pk})
        self.assertFalse(round.invitations.filter(user=self.other).exists())
        self.assertEqual(round.answers.count(),0);self.assertEqual(responses_for(self.activity),[])
        self.client.force_login(self.alice)
        detail=self.client.get(self.activity.get_absolute_url())
        self.assertContains(detail,'Prior response (separate from this confirmation)')
        self.assertNotContains(detail,'You: Going');self.assertContains(detail,'Selected date')
        self.assertContains(detail,'Keep original question evidence')
        self.assertEqual(ActivityResponse.objects.values().get(pk=prior.pk),snapshot)

    def test_repeat_finalization_is_idempotent_and_does_not_reopen_or_reinvite(self):
        self.vote();round=self.finalize();event=ActivityNotificationEvent.objects.get(kind='confirmation')
        old=list(ConfirmationInvitation.objects.values())
        self.assertIn('already finalized',finalize_poll(self.activity.pk,self.host,self.options[2].pk))
        self.assertEqual(ConfirmationRound.objects.count(),1);self.assertEqual(AttendanceAnswer.objects.count(),0)
        self.assertEqual(ActivityNotificationEvent.objects.get().pk,event.pk)
        self.assertEqual(list(ConfirmationInvitation.objects.values()),old)
        round.refresh_from_db();self.assertEqual(round.selected_option_id,self.options[1].pk)
        before=list(DatePollSubmission.objects.values());self.vote(values=('no','no','no'))
        self.assertEqual(list(DatePollSubmission.objects.values()),before)

    def test_only_authorized_organizer_can_finalize_and_option_must_belong_to_poll(self):
        url=reverse('activities:poll_finalize',args=[self.activity.pk])
        self.assertEqual(self.client.post(url,{'option':self.options[0].pk}).status_code,404)
        self.client.force_login(self.host)
        second=Activity.objects.create(host=self.host,title='Different plan',cost_type='free',participation_config=make_config('planning',version=3))
        otherpoll=create_poll(second,self.dates)
        self.assertEqual(self.client.post(url,{'option':otherpoll.options.first().pk}).status_code,404)
        self.assertFalse(ConfirmationRound.objects.exists())
        group=Group.objects.create(owner=self.host,name='Optional hikers')
        GroupMembership.objects.create(group=group,user=self.other,role='organizer')
        self.activity.group=group;self.activity.save(update_fields=['group'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url,{'option':self.options[0].pk}).status_code,302)
        self.assertEqual(ConfirmationRound.objects.get().finalized_by_id,self.other.pk)

    def test_existing_secured_places_block_finalization_without_releasing_or_reinterpreting(self):
        old=ActivityResponse.objects.create(activity=self.activity,user=self.alice,status='committed',note='Original seat')
        before=ActivityResponse.objects.values().get(pk=old.pk)
        self.assertIn('need review',finalize_poll(self.activity.pk,self.host,self.options[0].pk))
        self.assertFalse(ConfirmationRound.objects.exists());self.assertFalse(ConfirmationInvitation.objects.exists())
        self.assertEqual(ActivityResponse.objects.values().get(pk=old.pk),before)
        self.activity.refresh_from_db();self.assertIsNone(self.activity.starts_at)

    def test_new_round_invites_all_no_participant_and_preserves_visibility_boundaries(self):
        self.vote();self.vote(self.bob,('no','no','no'))
        self.activity.audience='friends';self.activity.save(update_fields=['audience'])
        Friendship.objects.create(user_a=self.host,user_b=self.alice)
        round=self.finalize()
        self.assertTrue(round.invitations.filter(user=self.bob).exists())
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.activity.get_absolute_url()).status_code,404)
        self.assertNotContains(self.client.get('/?q=Tentative'),'Tentative Hersheypark')
        self.assertEqual(self.respond(user=self.bob).status_code,404)
        delivery=ActivityNotificationDelivery.objects.get(event__confirmation_round=round,recipient=self.bob)
        self.assertEqual(delivery.reason,'recipient_no_access')
        self.assertEqual(AttendanceAnswer.objects.count(),0)

    def test_round_specific_confirmations_capacity_toggle_decline_and_withdrawal_preserve_history(self):
        self.vote();self.vote(self.bob,('no','no','no'));round=self.finalize()
        prior=ActivityResponse.objects.create(activity=self.activity,user=self.alice,status='interested',note='Read-only prior evidence')
        before=ActivityResponse.objects.values().get(pk=prior.pk)
        self.assertContains(self.respond(user=self.alice),'You: Going')
        self.assertEqual(recipient_ids(self.activity),{self.alice.pk})
        self.assertContains(self.respond(user=self.bob),'full. Your response has not changed')
        self.assertFalse(round.answers.filter(user=self.bob).exists())
        self.assertContains(self.respond('decline_attendance',user=self.bob),"You: Can&#x27;t make it")
        self.respond('decline_attendance',user=self.alice)
        self.respond(user=self.bob)
        self.assertEqual(sum(r.status=='committed' for r in responses_for(self.activity)),1)
        self.respond(user=self.bob) # select again to withdraw
        self.assertEqual(round.answers.filter(user=self.bob).last().status,'withdrawn')
        self.assertEqual(sum(r.status=='committed' for r in responses_for(self.activity)),0)
        self.respond(user=self.alice)
        self.client.post(reverse('activities:leave',args=[self.activity.pk]),{'confirmation_round':round.pk})
        self.assertEqual(round.answers.filter(user=self.alice).last().status,'withdrawn')
        self.assertEqual(ActivityResponse.objects.values().get(pk=prior.pk),before)
        self.assertEqual(DatePollSubmission.objects.count(),2)
        self.assertGreater(round.answers.count(),2)

    def test_stale_missing_or_foreign_round_and_forged_legacy_status_cannot_change_attendance(self):
        round=self.finalize();route=reverse('activities:respond',args=[self.activity.pk])
        for data in [{'action':'confirm_attendance'}, {'action':'confirm_attendance','confirmation_round':round.pk+1},
                     {'status':'committed','confirmation_round':round.pk}, {'action':'answer_poll','confirmation_round':round.pk}]:
            self.client.post(route,data)
        self.client.post(reverse('activities:join',args=[self.activity.pk]))
        self.assertFalse(AttendanceAnswer.objects.exists());self.assertFalse(ActivityResponse.objects.exists())
        self.client.post(reverse('activities:join',args=[self.activity.pk]),{'confirmation_round':round.pk})
        before=list(AttendanceAnswer.objects.values())
        self.client.post(reverse('activities:join',args=[self.activity.pk]),{'confirmation_round':round.pk})
        self.client.post(reverse('activities:leave',args=[self.activity.pk]))
        self.assertEqual(list(AttendanceAnswer.objects.values()),before)

    def test_cancel_closes_poll_finalize_and_confirmation_without_deleting_history(self):
        self.vote();before=list(DatePollSubmission.objects.values())
        cancel_activity(self.activity.pk,self.host,'Closed')
        self.vote(values=('no','no','no'))
        self.assertIn('cancelled',finalize_poll(self.activity.pk,self.host,self.options[0].pk))
        self.assertEqual(list(DatePollSubmission.objects.values()),before)
        self.assertFalse(ConfirmationRound.objects.exists())
        # A second occurrence demonstrates finalized cancellation independently.
        a=Activity.objects.create(host=self.host,title='Second plan',cost_type='free',participation_config=make_config('planning',version=3))
        p=create_poll(a,self.dates);finalize_poll(a.pk,self.host,p.options.first().pk)
        from .participation import change_response
        r=a.attendance_round;change_response(a.pk,self.alice,action='confirm_attendance',confirmation_round=r.pk)
        old=list(AttendanceAnswer.objects.filter(round=r).values())
        cancel_activity(a.pk,self.host,'Weather')
        change_response(a.pk,self.alice,action='decline_attendance',confirmation_round=r.pk)
        change_response(a.pk,self.alice,confirmation_round=r.pk,remove=True)
        self.assertEqual(list(AttendanceAnswer.objects.filter(round=r).values()),old)

    def test_ordinary_nonparticipant_can_confirm_without_becoming_poll_participant_or_group_member(self):
        self.vote();round=self.finalize()
        self.assertContains(self.client.get('/?q=Tentative'),'confirm_attendance')
        self.client.force_login(self.other)
        page=self.client.get('/?q=Tentative')
        self.assertNotContains(page,'confirm_attendance');self.assertContains(page,'See details')
        self.respond(user=self.other)
        self.assertEqual(round.answers.filter(user=self.other).last().status,'committed')
        self.assertFalse(DatePollSubmission.objects.filter(user=self.other).exists())
        self.assertFalse(round.invitations.filter(user=self.other).exists())
        self.assertFalse(GroupMembership.objects.exists())

    def test_htmx_and_non_js_poll_and_confirmation_preserve_filtered_return(self):
        destination='/?q=Tentative&audience=everyone&audience=friends'
        self.vote(next=destination)
        self.assertContains(self.client.get('/?q=Tentative'),'Poll answered / Edit answers')
        fallback=self.client.post(reverse('activities:poll_vote',args=[self.activity.pk]),
            {**self.answers(('maybe','maybe','no')),'variant':'detail','next':destination})
        self.assertEqual(fallback.status_code,302);self.assertEqual(fallback.url,destination)
        round=self.finalize()
        fragment=self.respond(round=round,variant='card',next=destination)
        self.assertContains(fragment,'confirm_attendance" aria-pressed="true"')
        self.assertContains(fragment,f'name="confirmation_round" value="{round.pk}"')
        fallback=self.client.post(reverse('activities:respond',args=[self.activity.pk]),
            {'action':'decline_attendance','confirmation_round':round.pk,'variant':'detail','next':destination})
        self.assertEqual(fallback.url,destination)
        self.assertNotEqual(responses_for(self.activity)[0].status,'committed')
        self.assertEqual(self.client.get(reverse('activities:roster',args=[self.activity.pk])).status_code,404)

    def test_confirmation_email_all_no_address_consent_sender_access_and_fixed_privacy(self):
        self.vote();self.vote(self.bob,('no','no','no'))
        with self.captureOnCommitCallbacks(execute=True):round=self.finalize()
        self.assertEqual(len(mail.outbox),2)
        self.assertEqual({m.to[0] for m in mail.outbox},{self.alice.email,self.bob.email})
        for message in mail.outbox:
            self.assertEqual(message.subject,'Please confirm attendance — Belong')
            self.assertIn('https://belong.example'+self.activity.get_absolute_url(),message.body)
            self.assertNotIn(self.activity.title,message.body);self.assertNotIn(self.activity.description,message.body)
        self.assertFalse(ActivityResponse.objects.exists());self.assertFalse(AttendanceAnswer.objects.exists())
        self.assertEqual(round.invitations.count(),2)
        deliver_event(ActivityNotificationEvent.objects.get(kind='confirmation').pk)
        self.assertEqual(len(mail.outbox),2)

    def test_inapp_invites_exist_when_email_opted_out_or_unverified(self):
        self.vote();self.vote(self.bob,('no','no','no'))
        self.alice.profile.activity_email_enabled=False;self.alice.profile.save()
        self.bob.profile.email_verified_at=None;self.bob.profile.save()
        with self.captureOnCommitCallbacks(execute=True):round=self.finalize()
        self.assertEqual(round.invitations.count(),2);self.assertEqual(len(mail.outbox),0)
        self.assertEqual(set(round.activitynotificationevent.deliveries.values_list('reason',flat=True)),{'recipient_opted_out','recipient_unverified'})

    def test_pending_confirmation_rechecks_consent_visibility_address_and_cancellation(self):
        self.vote();self.vote(self.bob);round=self.finalize()
        event=ActivityNotificationEvent.objects.get(confirmation_round=round)
        self.alice.email='changed@example.invalid';self.alice.save()
        self.bob.profile.activity_email_enabled=False;self.bob.profile.save()
        deliver_event(event.pk)
        self.assertEqual(set(event.deliveries.values_list('reason',flat=True)),{'recipient_address_changed','recipient_opted_out'})
        self.assertEqual(len(mail.outbox),0)
        event.deliveries.update(status='pending',reason='')
        cancel_activity(self.activity.pk,self.host,'Closed')
        self.bob.profile.activity_email_enabled=True;self.bob.profile.save()
        deliver_event(event.pk)
        self.assertIn('superseded_by_cancellation',set(event.deliveries.values_list('reason',flat=True)))
        self.assertEqual(len(mail.outbox),0)

    def test_confirmation_delivery_failure_and_retry_do_not_duplicate_inapp_invites_or_history(self):
        self.vote();round=self.finalize();event=ActivityNotificationEvent.objects.get(confirmation_round=round)
        with patch('activities.notifications.EMAIL_TRANSPORT',side_effect=RuntimeError):deliver_event(event.pk)
        delivery=event.deliveries.get();self.assertEqual(delivery.status,'failed')
        self.assertEqual(round.invitations.count(),1);self.assertFalse(AttendanceAnswer.objects.exists())
        delivery.retry_at=timezone.now();delivery.save()
        self.assertTrue(deliver_one(delivery.pk));self.assertEqual(len(mail.outbox),1)
        self.assertFalse(deliver_one(delivery.pk));self.assertEqual(len(mail.outbox),1)

    def test_poll_only_participants_are_not_routine_update_recipients_but_confirmed_attendees_are(self):
        self.vote();self.vote(self.bob);round=self.finalize()
        from .participation import locked_activity
        with locked_activity(self.activity.pk) as a:
            ann=Announcement.objects.create(activity=a,author=self.host,body='Before attendance')
            ann.recipients.set(recipient_ids(a));event=queue_event(a,self.host,'update',announcement=ann)
        self.assertEqual(event.deliveries.count(),0)
        self.respond(user=self.alice)
        with locked_activity(self.activity.pk) as a:
            ann=Announcement.objects.create(activity=a,author=self.host,body='For attendees')
            ann.recipients.set(recipient_ids(a));event=queue_event(a,self.host,'update',announcement=ann)
        self.assertEqual(list(event.deliveries.values_list('recipient_id',flat=True)),[self.alice.pk])
        self.assertTrue(updates_for(a,self.alice,organizer=False).filter(pk=ann.pk).exists())
        self.assertFalse(updates_for(a,self.bob,organizer=False).exists())
        self.respond('decline_attendance',user=self.alice)
        self.assertFalse(updates_for(a,self.alice,organizer=False).exists())

    def test_finalized_date_is_immutable_and_pending_notice_stops_after_answering(self):
        self.vote(); round=self.finalize()
        self.activity.refresh_from_db(); self.activity.starts_at=self.options[2].starts_at
        with self.assertRaises(ValidationError): self.activity.save(update_fields=['starts_at'])
        self.respond(user=self.alice)
        event=ActivityNotificationEvent.objects.get(confirmation_round=round)
        deliver_event(event.pk)
        self.assertEqual(event.deliveries.get().reason,'confirmation_already_answered')
        self.assertEqual(len(mail.outbox),0)

    def test_confirmation_respects_sender_authority_and_shared_actor_budget(self):
        from django.conf import settings
        self.vote(); round=self.finalize(); event=ActivityNotificationEvent.objects.get(confirmation_round=round)
        self.host.profile.outbound_mail_suspended=True; self.host.profile.save()
        deliver_event(event.pk)
        self.assertEqual(event.deliveries.get().reason,'sender_suspended')
        self.assertEqual(round.invitations.count(),1); self.assertEqual(len(mail.outbox),0)
        self.host.profile.outbound_mail_suspended=False; self.host.profile.save()
        event.deliveries.update(status='pending',reason='')
        for n in range(settings.EMAIL_LIMITS['invitation_attempts_day']):
            OutboundEmailAttempt.objects.create(kind='invitation',actor=self.host,recipient_hash='0'*64,ip_hash='',outcome='sent')
        deliver_event(event.pk)
        delivery=event.deliveries.get()
        self.assertEqual(delivery.status,'pending'); self.assertEqual(delivery.reason,'actor_day')
        self.assertEqual(delivery.attempts,0); self.assertEqual(len(mail.outbox),0)

    def test_optional_group_join_uses_real_round_response_not_poll_answers(self):
        group=Group.objects.create(owner=self.host,name='Optional trip group',access='open')
        self.activity.group=group;self.activity.save(update_fields=['group'])
        self.vote();self.assertIsNone(current_offer(self.alice))
        round=self.finalize();self.respond(user=self.alice)
        self.assertIsNotNone(current_offer(self.alice))
        self.assertFalse(GroupMembership.objects.filter(group=group,user=self.alice).exists())
        url=reverse('activities:answer_group_offer',args=[self.activity.pk])
        self.assertEqual(self.client.post(url,{'action':'join'}).status_code,302)
        self.assertTrue(GroupMembership.objects.filter(group=group,user=self.alice,status='active').exists())
        self.assertEqual(round.answers.filter(user=self.alice).last().status,'committed')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_history_is_read_only_in_admin(self):
        from .admin import NotificationAuditAdmin
        request=RequestFactory().get('/admin/');request.user=self.host
        for model in [DatePoll,DatePollOption,DatePollSubmission,ConfirmationRound,ConfirmationInvitation,AttendanceAnswer]:
            audit=NotificationAuditAdmin(model,AdminSite())
            self.assertFalse(audit.has_add_permission(request));self.assertFalse(audit.has_change_permission(request));self.assertFalse(audit.has_delete_permission(request))


class PollMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_every_prior_activity_response_and_notification_field(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes();old=[('activities','0024_activity_participation_config_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            user=apps.get_model('auth','User').objects.create(username='poll-migration')
            a=apps.get_model('activities','Activity').objects.create(host_id=user.pk,title='Keep legacy',available_responses=['interested','vote'])
            apps.get_model('activities','ActivityResponse').objects.create(activity_id=a.pk,user_id=user.pk,status='interested',note='Retain history')
            ann=apps.get_model('activities','Announcement').objects.create(activity_id=a.pk,author_id=user.pk,body='Old update')
            evt=apps.get_model('activities','ActivityNotificationEvent').objects.create(activity_id=a.pk,announcement_id=ann.pk,actor_id=user.pk,kind='update')
            apps.get_model('activities','ActivityNotificationDelivery').objects.create(event_id=evt.pk,recipient_id=user.pk,recipient_hash='0'*64,status='sent',attempts=1)
            snapshots={name:list(apps.get_model('activities',name).objects.values()) for name in ['Activity','ActivityResponse','Announcement','ActivityNotificationEvent','ActivityNotificationDelivery']}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as live
            for name,rows in snapshots.items():self.assertEqual(list(live.get_model('activities',name).objects.values(*rows[0].keys())),rows,name)
            self.assertEqual(DatePoll.objects.count(),0);self.assertEqual(ConfirmationRound.objects.count(),0)
        finally:MigrationExecutor(connection).migrate(leaves)


class PollConcurrencyTests(SimpleTestCase):
    def test_file_backed_vote_finalize_cancel_and_last_seat_races(self):
        with tempfile.TemporaryDirectory() as root:
            env={**os.environ,'DJANGO_SETTINGS_MODULE':'belong.settings','BELONG_ENV':'test',
                 'DJANGO_DB_PATH':str(Path(root)/'poll-races.sqlite3'),'DJANGO_ALLOWED_HOSTS':'testserver'}
            code='''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.management import call_command
from django.db import connections
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from belong.test_helpers import create_legacy_user
from activities.models import Activity, ConfirmationInvitation, AttendanceAnswer, DatePollSubmission
from activities.participation_config import make_config
from activities.polls import create_poll, finalize_poll, submit_answers, responses_for
call_command('migrate',verbosity=0)
users=[create_legacy_user('poll-race-'+str(i)) for i in range(5)]
clients=[]
for user in users:
    c=Client();c.force_login(user);clients.append(c)
def setup():
    a=Activity.objects.create(host=users[0],title='Race plan',cost_type='free',capacity=1,participation_config=make_config('planning',version=3))
    p=create_poll(a,[timezone.now()+timezone.timedelta(days=n) for n in (10,11,12)])
    options=list(p.options.all());data={'option_'+str(o.pk):'no' for o in options}
    return a,p,options,data
for iteration in range(3):
    a,p,options,data=setup();barrier=Barrier(2)
    def vote_or_finalize(i):
        barrier.wait(timeout=10)
        try:
            if i==0:submit_answers(a.pk,users[1],data)
            else:finalize_poll(a.pk,users[0],options[0].pk)
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(vote_or_finalize,range(2)))
    assert p.submissions.filter(user=users[1]).exists()==ConfirmationInvitation.objects.filter(round__poll=p,user=users[1]).exists()
    assert not AttendanceAnswer.objects.filter(round__poll=p).exists()
    assert not a.responses.exists()
for iteration in range(3):
    a,p,options,data=setup();submit_answers(a.pk,users[1],data);barrier=Barrier(2)
    def finalize_or_cancel(i):
        barrier.wait(timeout=10)
        try:
            route='poll_finalize' if i==0 else 'cancel'
            r=clients[0].post(reverse('activities:'+route,args=[a.pk]),{'option':options[0].pk,'reason':'Closed'})
            assert r.status_code==302,r.status_code
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(finalize_or_cancel,range(2)))
    a.refresh_from_db();assert a.is_cancelled
    r=a.attendance_round
    if r:
        assert r.created_at<=a.cancelled_at
        before=list(r.answers.values())
        clients[1].post(reverse('activities:respond',args=[a.pk]),{'action':'confirm_attendance','confirmation_round':r.pk})
        assert list(r.answers.values())==before
    else:assert not ConfirmationInvitation.objects.filter(round__poll=p).exists()
    assert p.submissions.count()==1
for iteration in range(3):
    a,p,options,data=setup();submit_answers(a.pk,users[1],data);finalize_poll(a.pk,users[0],options[0].pk)
    r=a.attendance_round;barrier=Barrier(4)
    def confirm(i):
        barrier.wait(timeout=10)
        try:
            response=clients[i].post(reverse('activities:respond',args=[a.pk]),{'action':'confirm_attendance','confirmation_round':r.pk})
            assert response.status_code==200,response.status_code
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(confirm,range(1,5)))
    assert sum(row.status=='committed' for row in responses_for(a))==1
    assert not a.responses.exists()
'''
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
