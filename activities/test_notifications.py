from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.db import transaction, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.email_controls import address_hash
from belong.test_helpers import create_legacy_user
from social.models import OutboundEmailAttempt
from .models import Activity, ActivityResponse, ActivityInvitation, Announcement, ActivityNotificationEvent, ActivityNotificationDelivery
from .notifications import queue_event, deliver_event, deliver_one, drain_notifications
from .participation import locked_activity, cancel_activity


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
class ActivityNotificationTests(TestCase):
    def setUp(self):
        self.host = self.person('notice-host')
        self.user = self.person('notice-person')
        self.activity = Activity.objects.create(host=self.host, title='Secret hike <script>', description='Private meeting point')
        ActivityResponse.objects.create(activity=self.activity, user=self.user, status='committed', note='Keep history')

    def person(self, name, **kwargs):
        user = create_legacy_user(name, email=name+'@example.invalid')
        user.profile.email_verified_at = timezone.now()
        user.profile.activity_email_enabled = True
        for key, value in kwargs.items():
            setattr(user.profile, key, value)
        user.profile.save()
        return user

    def event(self, body='Secret weather <script>'):
        with locked_activity(self.activity.pk) as activity:
            announcement = Announcement.objects.create(activity=activity, author=self.host, body=body)
            return queue_event(activity, self.host, 'update', announcement=announcement)

    def post_update(self, token=None, body='Trailhead moved'):
        self.client.force_login(self.host)
        url = reverse('activities:announce', args=[self.activity.pk])
        if token is None:
            token = self.client.get(url).context['form'].initial['submission_token']
        return self.client.post(url, {'body': body, 'submission_token': token})

    def test_update_after_commit_fixed_private_single_recipient_email_and_canonical_links(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_update().status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.user.email])
        self.assertEqual(message.subject, 'Activity update — Belong')
        self.assertIn('https://belong.example'+self.activity.get_absolute_url(), message.body)
        self.assertIn('https://belong.example/accounts/settings/', message.body)
        for secret in [self.activity.title, self.activity.description, 'Trailhead moved', 'script']:
            self.assertNotIn(secret, message.body)
        self.assertFalse(message.cc); self.assertFalse(message.bcc)
        self.assertEqual(ActivityNotificationDelivery.objects.get().status, 'sent')
        self.assertEqual(OutboundEmailAttempt.objects.get().outcome, 'sent')

    def test_all_non_declined_responses_including_historical_receive_not_invited_nonresponders_or_actor(self):
        for status in ['question', 'more', 'vote', 'interested', 'declined']:
            user = self.person('state-'+status)
            ActivityResponse.objects.create(activity=self.activity, user=user, status=status)
        invited = self.person('invited-only')
        ActivityInvitation.objects.create(activity=self.activity, user=invited, invited_by=self.host)
        ActivityResponse.objects.create(activity=self.activity, user=self.host, status='committed')
        event = self.event(); deliver_event(event.pk)
        self.assertEqual(len(mail.outbox), 5)
        addresses = {m.to[0] for m in mail.outbox}
        self.assertNotIn(invited.email, addresses); self.assertNotIn(self.host.email, addresses)
        self.assertNotIn('state-declined@example.invalid', addresses)

    def test_consent_verified_current_email_required_no_legacy_bypass(self):
        for name, props in [('unverified', {'email_verified_at': None}), ('optout', {'activity_email_enabled': False})]:
            user = self.person(name, **props)
            ActivityResponse.objects.create(activity=self.activity, user=user, status='more')
        noemail = self.person('noemail'); noemail.email=''; noemail.save()
        inactive = self.person('inactive'); inactive.is_active=False; inactive.save()
        for user in [noemail, inactive]:
            ActivityResponse.objects.create(activity=self.activity, user=user, status='question')
        event = self.event(); deliver_event(event.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(set(event.deliveries.filter(status='skipped').values_list('reason', flat=True)),
                         {'recipient_unverified','recipient_opted_out','recipient_no_email','recipient_inactive'})

    def test_snapshot_never_expands_for_late_responders_or_later_opt_in(self):
        self.user.profile.activity_email_enabled=False; self.user.profile.save()
        event = self.event()
        self.user.profile.activity_email_enabled=True; self.user.profile.save()
        late = self.person('late')
        ActivityResponse.objects.create(activity=self.activity, user=late, status='committed')
        deliver_event(event.pk)
        self.assertEqual(event.deliveries.count(), 1)
        self.assertEqual(event.deliveries.get().status, 'skipped')
        self.assertEqual(len(mail.outbox), 0)

    def test_recipient_changes_rechecked_before_send_and_retry(self):
        for change in ['address', 'unverify', 'optout', 'decline', 'remove', 'visibility', 'inactive']:
            with self.subTest(change=change):
                user = self.person('change-'+change)
                ActivityResponse.objects.create(activity=self.activity, user=user, status='more')
                event = self.event()
                delivery = event.deliveries.get(recipient=user)
                if change == 'address': user.email='changed@example.invalid'; user.save()
                if change == 'unverify': user.profile.email_verified_at=None; user.profile.save()
                if change == 'optout': user.profile.activity_email_enabled=False; user.profile.save()
                if change == 'decline': ActivityResponse.objects.filter(user=user).update(status='declined')
                if change == 'remove': ActivityResponse.objects.filter(user=user).delete()
                if change == 'visibility': self.activity.audience='friends'; self.activity.save()
                if change == 'inactive': user.is_active=False; user.save()
                self.assertFalse(deliver_one(delivery.pk)); delivery.refresh_from_db()
                self.assertEqual(delivery.status, 'skipped')
                self.activity.audience='everyone'; self.activity.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_sender_unverified_suspended_or_demoted_cannot_send_but_in_app_update_survives(self):
        for attribute in ['email_verified_at', 'outbound_mail_suspended']:
            setattr(self.host.profile, attribute, None if attribute == 'email_verified_at' else True); self.host.profile.save()
            with self.captureOnCommitCallbacks(execute=True): self.post_update()
            self.assertEqual(ActivityNotificationDelivery.objects.latest('pk').status, 'skipped')
            self.host.profile.email_verified_at=timezone.now(); self.host.profile.outbound_mail_suspended=False; self.host.profile.save()
        event = self.event(); self.activity.host=self.user; self.activity.save()
        deliver_event(event.pk)
        self.assertEqual(event.deliveries.get().reason, 'sender_not_organizer')
        self.assertEqual(Announcement.objects.count(), 3); self.assertEqual(len(mail.outbox), 0)

    def test_success_and_duplicate_publication_never_resend_or_duplicate_announcements(self):
        self.client.force_login(self.host)
        token = self.client.get(reverse('activities:announce', args=[self.activity.pk])).context['form'].initial['submission_token']
        with self.captureOnCommitCallbacks(execute=True):
            self.post_update(token); self.post_update(token, body='Changed repeat body')
        event = ActivityNotificationEvent.objects.get()
        deliver_event(event.pk); drain_notifications()
        self.assertEqual(Announcement.objects.count(), 1); self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(event.deliveries.get().attempts, 1)

    def test_missing_forged_or_cross_occurrence_submission_token_rejected(self):
        for token in ['', 'forged']:
            self.assertEqual(self.post_update(token).status_code, 200)
        self.client.force_login(self.host)
        token = self.client.get(reverse('activities:announce', args=[self.activity.pk])).context['form'].initial['submission_token']
        other = Activity.objects.create(host=self.host, title='Other', description='Other')
        self.assertEqual(self.client.post(reverse('activities:announce', args=[other.pk]), {'body':'X','submission_token':token}).status_code, 200)
        self.assertFalse(Announcement.objects.exists())

    def test_cancellation_idempotent_urgent_and_preserves_response_history(self):
        before = list(ActivityResponse.objects.values())
        with self.captureOnCommitCallbacks(execute=True):
            cancel_activity(self.activity.pk, self.host, 'Storm and private location')
            cancel_activity(self.activity.pk, self.host, 'Repeat')
        self.assertEqual(ActivityNotificationEvent.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Activity cancelled — Belong')
        self.assertIn('before travelling', mail.outbox[0].body)
        self.assertNotIn('Storm', mail.outbox[0].body)
        self.assertEqual(list(ActivityResponse.objects.values()), before)
        self.activity.refresh_from_db(); self.assertEqual(self.activity.cancellation_reason, 'Storm and private location')

    def test_cancellation_before_update_delivery_skips_obsolete_update_but_allows_later_coordination(self):
        earlier = self.event()
        cancel_activity(self.activity.pk, self.host, 'Storm')
        deliver_event(earlier.pk)
        self.assertEqual(earlier.deliveries.get().reason, 'superseded_by_cancellation')
        later = self.event('Refund coordination'); deliver_event(later.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_failures_bounded_backoff_and_retry_rechecks_address(self):
        event = self.event(); delivery = event.deliveries.get()
        with patch('belong.email_controls.send_mail', side_effect=RuntimeError('secret payload')):
            self.assertFalse(deliver_one(delivery.pk))
            self.assertFalse(deliver_one(delivery.pk))
            delivery.refresh_from_db(); self.assertEqual(delivery.attempts, 1)
            self.assertEqual(delivery.status, 'failed'); self.assertNotIn('secret', delivery.reason)
            for _ in range(2):
                ActivityNotificationDelivery.objects.filter(pk=delivery.pk).update(retry_at=timezone.now()-timedelta(seconds=1))
                deliver_one(delivery.pk)
        delivery.refresh_from_db(); self.assertEqual(delivery.attempts, 3)
        self.assertEqual(drain_notifications(), 0)
        self.assertEqual(OutboundEmailAttempt.objects.count(), 3)
        second=self.event(); deliver=second.deliveries.get()
        with patch('belong.email_controls.send_mail', return_value=0): deliver_one(deliver.pk)
        self.user.email='other-address@example.invalid'; self.user.save()
        ActivityNotificationDelivery.objects.filter(pk=deliver.pk).update(retry_at=timezone.now()-timedelta(seconds=1))
        self.assertFalse(deliver_one(deliver.pk)); deliver.refresh_from_db()
        self.assertEqual(deliver.reason, 'recipient_address_changed')

    def test_retry_can_succeed_once_and_origin_failure_is_audited(self):
        event=self.event(); delivery=event.deliveries.get()
        with override_settings(BELONG_PUBLIC_ORIGIN='https://evil.example/arbitrary-path'):
            self.assertFalse(deliver_one(delivery.pk))
        delivery.refresh_from_db(); self.assertEqual(delivery.status, 'failed')
        ActivityNotificationDelivery.objects.filter(pk=delivery.pk).update(retry_at=timezone.now()-timedelta(seconds=1))
        self.assertTrue(deliver_one(delivery.pk)); self.assertFalse(deliver_one(delivery.pk))
        self.assertEqual(len(mail.outbox), 1)

    def test_cancellation_budget_and_priority_independent_of_updates(self):
        for _ in range(50):
            OutboundEmailAttempt.objects.create(kind='invitation', actor=self.host, recipient_hash=address_hash(self.user.email), ip_hash='')
        update=self.event()
        self.assertFalse(deliver_one(update.deliveries.get().pk))
        self.assertEqual(update.deliveries.get().reason, 'actor_day')
        cancel_activity(self.activity.pk,self.host,'Storm')
        self.assertEqual(drain_notifications(limit=1), 1)
        self.assertEqual(mail.outbox[0].subject, 'Activity cancelled — Belong')

    def test_recipient_hour_ceiling_stops_update_relay_without_consuming_attempt_budget(self):
        for _ in range(3):
            event=self.event(); deliver_event(event.pk)
        event=self.event(); delivery=event.deliveries.get()
        self.assertFalse(deliver_one(delivery.pk)); delivery.refresh_from_db()
        self.assertEqual(delivery.reason, 'recipient_hour'); self.assertEqual(delivery.attempts, 0)
        self.assertEqual(OutboundEmailAttempt.objects.latest('pk').outcome, 'blocked')

    def test_ambiguous_smtp_disconnect_is_not_blindly_retried(self):
        from smtplib import SMTPServerDisconnected
        event=self.event(); delivery=event.deliveries.get()
        with patch('belong.email_controls.send_mail', side_effect=SMTPServerDisconnected('Lost acknowledgement')):
            self.assertFalse(deliver_one(delivery.pk))
        delivery.refresh_from_db(); self.assertEqual(delivery.status, 'unknown')
        self.assertEqual(drain_notifications(), 0)

    def test_stale_claim_unknown_not_automatically_resent(self):
        event=self.event(); delivery=event.deliveries.get()
        ActivityNotificationDelivery.objects.filter(pk=delivery.pk).update(status='sending', updated_at=timezone.now()-timedelta(minutes=16))
        self.assertEqual(drain_notifications(), 0); delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'unknown'); self.assertFalse(deliver_one(delivery.pk))

    def test_global_preference_defaults_off_and_profile_save_does_not_change_it(self):
        new=create_legacy_user('default-optout')
        self.assertFalse(new.profile.activity_email_enabled)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('account_settings')), 'Email me Activity updates and cancellations')
        self.client.post(reverse('account_settings'), {'action':'profile','display_name':'New name','account_type':'individual','location':''})
        self.user.profile.refresh_from_db(); self.assertTrue(self.user.profile.activity_email_enabled)
        self.client.post(reverse('account_settings'), {'action':'notifications'})
        self.user.profile.refresh_from_db(); self.assertFalse(self.user.profile.activity_email_enabled)
        self.client.post(reverse('account_settings'), {'action':'notifications','activity_email_enabled':'on'})
        self.user.profile.refresh_from_db(); self.assertTrue(self.user.profile.activity_email_enabled)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationTransactionTests(TransactionTestCase):
    def test_no_smtp_on_rollback_and_after_commit_observes_saved_cancellation(self):
        from social.models import EmailControlLock
        EmailControlLock.objects.get_or_create(pk=1)
        host=create_legacy_user('tx-host', email='tx-host@example.invalid')
        user=create_legacy_user('tx-user', email='tx-user@example.invalid')
        for person in [host,user]:
            person.profile.email_verified_at=timezone.now(); person.profile.activity_email_enabled=True; person.profile.save()
        activity=Activity.objects.create(host=host,title='Transaction',description='Tx')
        ActivityResponse.objects.create(activity=activity,user=user,status='more')
        with self.assertRaises(RuntimeError), transaction.atomic():
            cancel_activity(activity.pk,host,'Rollback')
            self.assertFalse(mail.outbox)
            raise RuntimeError('Rollback')
        self.assertFalse(ActivityNotificationEvent.objects.exists())
        activity.refresh_from_db(); self.assertFalse(activity.is_cancelled)
        def transport(event, attempt, email):
            self.assertFalse(connection.in_atomic_block)
            self.assertTrue(Activity.objects.get(pk=activity.pk).is_cancelled)
            OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='sent')
            return True
        with patch('activities.notifications.EMAIL_TRANSPORT', side_effect=transport):
            cancel_activity(activity.pk,host,'Committed')
        self.assertEqual(ActivityNotificationDelivery.objects.get().status, 'sent')


class NotificationMigrationTests(TransactionTestCase):
    def test_migration_does_not_replay_old_updates_or_rewrite_responses_or_enable_consent(self):
        from django.db.migrations.executor import MigrationExecutor
        executor=MigrationExecutor(connection); leaves=executor.loader.graph.leaf_nodes()
        old_targets=[('activities','0022_alter_activityresponse_status'),('social','0011_outboundemailattempt_activity_reference')]
        try:
            executor.migrate(old_targets)
            apps=executor.loader.project_state(old_targets).apps
            user=apps.get_model('auth','User').objects.create(username='historical-migration',email='old@example.invalid')
            apps.get_model('social','UserProfile').objects.create(user_id=user.pk,email_verified_at=timezone.now(),legacy_access=True)
            activity=apps.get_model('activities','Activity').objects.create(host_id=user.pk,title='Old',description='History',available_responses=['interested'])
            response=apps.get_model('activities','ActivityResponse').objects.create(activity_id=activity.pk,user_id=user.pk,status='interested',note='Keep')
            update=apps.get_model('activities','Announcement').objects.create(activity_id=activity.pk,author_id=user.pk,body='Old update')
            before=apps.get_model('activities','ActivityResponse').objects.values().get(pk=response.pk)
            executor=MigrationExecutor(connection); executor.migrate(leaves)
            self.assertEqual(ActivityResponse.objects.values().get(pk=response.pk),before)
            self.assertEqual(Activity.objects.get(pk=activity.pk).available_responses,['interested'])
            self.assertEqual(Announcement.objects.get(pk=update.pk).body,'Old update')
            from social.models import UserProfile
            self.assertFalse(UserProfile.objects.get(user_id=user.pk).activity_email_enabled)
            self.assertFalse(ActivityNotificationEvent.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
