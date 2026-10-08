import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.invitations import digest, issue_invitation as issue_group_invitation
from groups.models import Group, GroupMembership, GroupInvitation
from social.models import OutboundEmailAttempt
from .email_invitations import issue_invitation
from .models import Activity, ActivityEmailInvitation, ActivityInvitation, ActivityResponse


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
class ActivityEmailInvitationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Testing-only-817!'
        cls.host = create_legacy_user('email-host', email='host@example.com', password=cls.password)
        cls.user = create_legacy_user('email-recipient', email='hiker@example.com', password=cls.password)
        cls.wrong = create_legacy_user('email-wrong', email='other@example.com', password=cls.password)
        for user in [cls.host, cls.user, cls.wrong]:
            user.profile.email_verified_at = timezone.now()
            user.profile.save()
        cls.group = Group.objects.create(owner=cls.host, name='Private group', access='private')
        cls.activity = Activity.objects.create(host=cls.host, group=cls.group, title='Secret trail',
            description='Private logistics https://arbitrary.example/', available_responses=['question'])

    def setUp(self):
        self.client.force_login(self.host)
        self.request = RequestFactory().post('/', HTTP_HOST='attacker.example', REMOTE_ADDR='192.0.2.1')

    def send(self, email=None):
        self.assertTrue(issue_invitation(self.activity, self.host, email or self.user.email, self.request))
        return re.search(r'/activity-invitations/([^/]+)/', mail.outbox[-1].body).group(1)

    def url(self, token):
        return reverse('activities:email_invitation', args=[token])

    def setup_data(self):
        return {'display_name': 'New Hiker', 'account_type': 'individual',
                'password1': self.password, 'password2': self.password}

    def test_fixed_email_canonical_origin_digest_and_durable_duplicate_controls(self):
        token = self.send('HIKER@example.com')
        invitation = ActivityEmailInvitation.objects.get()
        self.assertEqual(invitation.email, self.user.email)
        self.assertEqual(invitation.token_digest, digest(token))
        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('https://belong.example'+self.url(token), mail.outbox[0].body)
        for text in [self.activity.title, self.activity.description, self.group.name, 'attacker.example']:
            self.assertNotIn(text, mail.outbox[0].body)
        with self.assertRaisesRegex(ValidationError, 'already emailed'):
            self.send()
        invitation.refresh_from_db()
        self.assertEqual(invitation.token_digest, digest(token))
        self.assertEqual(len(mail.outbox), 1)
        roster = self.client.get(reverse('activities:roster', args=[self.activity.pk]))
        self.assertContains(roster, self.user.email)
        self.assertNotContains(roster, token)
        self.assertNotContains(roster, invitation.token_digest)

    def test_existing_recipient_accepts_idempotently_then_rsvps_without_group_join(self):
        token = self.send()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.url(token)), self.activity.title)
        self.assertFalse(ActivityInvitation.objects.exists())
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url(token)), self.activity.get_absolute_url())
        self.assertEqual(ActivityInvitation.objects.filter(user=self.user).count(), 1)
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
        self.client.post(reverse('activities:respond', args=[self.activity.pk]), {'status': 'committed'})
        self.assertEqual(ActivityResponse.objects.get(user=self.user).status, 'committed')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_removed_direct_invitation_keeps_response_and_consumed_token_cannot_recreate(self):
        token = self.send()
        self.client.force_login(self.user)
        self.client.post(self.url(token))
        response = ActivityResponse.objects.create(activity=self.activity, user=self.user, status='question', note='Keep history')
        before = ActivityResponse.objects.values().get(pk=response.pk)
        invitation = ActivityInvitation.objects.get(user=self.user)
        self.client.force_login(self.host)
        self.client.post(reverse('activities:manage_invitations', args=[self.activity.pk]),
                         {'action': 'remove', 'invitation': invitation.pk})
        self.client.force_login(self.user)
        self.client.post(self.url(token))
        self.assertFalse(ActivityInvitation.objects.filter(user=self.user).exists())
        self.assertEqual(ActivityResponse.objects.values().get(pk=response.pk), before)

    def test_anonymous_and_wrong_account_never_see_activity_details(self):
        token = self.send()
        self.client.logout()
        for user in [None, self.wrong]:
            if user:
                self.client.force_login(user)
            page = self.client.get(self.url(token))
            self.assertEqual(page['Cache-Control'], 'no-store')
            self.assertEqual(page['Referrer-Policy'], 'same-origin')
            for text in [self.activity.title, self.activity.description, self.group.name]:
                self.assertNotContains(page, text)
        self.client.post(self.url(token))
        self.assertFalse(ActivityInvitation.objects.exists())
        self.assertFalse(GroupMembership.objects.exists())

    def test_login_continuation_wrong_account_switch_and_signed_id_only(self):
        token = self.send()
        self.client.logout()
        self.assertRedirects(self.client.post(self.url(token), {'auth': 'login'}), reverse('login'))
        self.assertEqual(self.client.session['pending_activity_invitation'], ActivityEmailInvitation.objects.get().pk)
        self.assertNotIn(token, str(dict(self.client.session)))
        response = self.client.post(reverse('login'), {'username': self.wrong.email, 'password': self.password})
        self.assertRedirects(response, reverse('activities:pending_email_invitation'))
        self.assertFalse(ActivityInvitation.objects.exists())
        self.assertRedirects(self.client.post(reverse('activities:pending_email_invitation'), {'auth': 'switch'}), reverse('login'))
        self.assertRedirects(self.client.post(reverse('login'), {'username': self.user.email, 'password': self.password}), self.activity.get_absolute_url())
        self.assertNotIn('pending_activity_invitation', self.client.session)
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_signup_owner_proof_interests_continuation_and_email_binding(self):
        token = self.send('new@example.com')
        self.client.logout()
        self.client.post(self.url(token), {'auth': 'signup'})
        self.assertContains(self.client.get(reverse('signup')), 'value="new@example.com"')
        self.assertContains(self.client.post(reverse('signup'), {'email': 'wrong@example.com'}), 'Use the invited email')
        self.assertRedirects(self.client.post(reverse('signup'), {'email': 'NEW@example.com'}), reverse('account_email_requested'))
        self.assertFalse(get_user_model().objects.filter(email='new@example.com').exists())
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        self.assertRedirects(self.client.post(reverse('complete_signup', args=[proof]), self.setup_data()), reverse('account_interests'))
        user = get_user_model().objects.get(email='new@example.com')
        self.assertTrue(user.profile.email_verified_at)
        self.assertTrue(ActivityInvitation.objects.filter(user=user).exists())
        self.assertFalse(ActivityResponse.objects.filter(user=user).exists())
        self.assertFalse(GroupMembership.objects.filter(user=user).exists())
        self.assertRedirects(self.client.post(reverse('account_interests'), {'action': 'skip'}), self.activity.get_absolute_url())

    def test_cross_browser_setup_continues_on_original_browser_login(self):
        token = self.send('cross@example.com')
        self.client.logout()
        self.client.post(self.url(token), {'auth': 'signup'})
        self.client.post(reverse('signup'), {'email': 'cross@example.com'})
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        other_browser = Client()
        other_browser.post(reverse('complete_signup', args=[proof]), self.setup_data())
        self.assertFalse(ActivityInvitation.objects.exists())
        self.client.post(reverse('login'), {'username': 'cross@example.com', 'password': self.password})
        self.assertTrue(ActivityInvitation.objects.filter(user__email='cross@example.com').exists())
        self.assertRedirects(self.client.post(reverse('account_interests'), {'action': 'skip'}), self.activity.get_absolute_url())

    def test_provisional_password_replacement_retains_only_matching_consented_invitation(self):
        provisional = get_user_model().objects.create_user('preclaim', email='preclaim@example.com', password='Old-password-817!')
        token = self.send(provisional.email)
        self.client.force_login(provisional)
        self.assertRedirects(self.client.post(self.url(token)), reverse('verification_status'))
        self.assertFalse(ActivityInvitation.objects.exists())
        self.client.post(reverse('verification_status'), {'email': provisional.email})
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        self.client.post(reverse('complete_signup', args=[proof]), self.setup_data())
        provisional.refresh_from_db()
        self.assertTrue(provisional.check_password(self.password))
        self.assertTrue(ActivityInvitation.objects.filter(user=provisional).exists())
        self.assertFalse(GroupMembership.objects.filter(user=provisional).exists())

    def test_account_recovery_keeps_activity_continuation_without_logging_in(self):
        token = self.send()
        self.client.logout()
        self.client.post(self.url(token), {'auth': 'login'})
        self.client.post(reverse('password_reset'), {'email': self.user.email})
        proof = re.search(r'/accounts/recover/([^/]+)/', mail.outbox[-1].body).group(1)
        password = 'Recovered-testing-817!'
        self.assertRedirects(self.client.post(reverse('complete_recovery', args=[proof]),
            {'new_password1': password, 'new_password2': password}), reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertIn('pending_activity_invitation', self.client.session)
        self.assertRedirects(self.client.post(reverse('login'), {'username': self.user.email, 'password': password}), self.activity.get_absolute_url())

    def test_invisible_activity_never_becomes_accessible_through_email(self):
        self.activity.audience = 'friends'
        self.activity.save()
        token = self.send()
        self.client.force_login(self.user)
        page = self.client.get(self.url(token))
        self.assertContains(page, 'not available to your account')
        self.assertNotContains(page, self.activity.title)
        self.assertNotContains(page, self.activity.description)
        self.client.post(self.url(token))
        self.assertFalse(ActivityInvitation.objects.exists())
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertEqual(self.client.get(self.activity.get_absolute_url()).status_code, 404)

    def test_expired_revoked_invalid_and_cross_occurrence_revoke(self):
        token = self.send()
        invitation = ActivityEmailInvitation.objects.get()
        self.client.force_login(self.user)
        for status, expires in [('pending', timezone.now()-timedelta(seconds=1)), ('revoked', timezone.now()+timedelta(days=1))]:
            ActivityEmailInvitation.objects.filter(pk=invitation.pk).update(status=status, expires_at=expires)
            self.assertNotContains(self.client.get(self.url(token)), self.activity.title)
            self.client.post(self.url(token))
            self.assertFalse(ActivityInvitation.objects.exists())
        self.assertNotContains(self.client.get(self.url('invalid-token')), self.activity.title)
        self.client.force_login(self.host)
        other = Activity.objects.create(host=self.host, title='Other')
        url = reverse('activities:revoke_email_invitation', args=[other.pk, invitation.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        ActivityEmailInvitation.objects.filter(pk=invitation.pk).update(status='pending')
        self.client.post(reverse('activities:revoke_email_invitation', args=[self.activity.pk, invitation.pk]))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'revoked')
        with self.assertRaisesRegex(ValidationError, 'already emailed'):
            self.send()

    def test_old_token_is_replaced_after_cooldown_without_modifying_responses(self):
        old = self.send()
        OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(days=8))
        token = self.send()
        self.assertNotEqual(old, token)
        self.assertEqual(ActivityEmailInvitation.objects.count(), 1)
        self.client.force_login(self.user)
        self.client.post(self.url(old))
        self.assertFalse(ActivityInvitation.objects.exists())
        self.client.post(self.url(token))
        self.assertTrue(ActivityInvitation.objects.exists())
        self.assertFalse(ActivityResponse.objects.exists())

    def test_verified_sender_suspension_and_current_authority(self):
        for verified, suspended, active, reason in [(None, False, True, 'Verify'), (timezone.now(), True, True, 'suspended'),
                                                    (timezone.now(), False, False, 'cannot send')]:
            self.host.profile.email_verified_at = verified
            self.host.profile.outbound_mail_suspended = suspended
            self.host.profile.save()
            self.host.is_active = active
            self.host.save()
            with self.assertRaisesRegex(ValidationError, reason):
                self.send()
        self.assertFalse(ActivityEmailInvitation.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(OutboundEmailAttempt.objects.filter(outcome='blocked').count(), 3)

    def test_post_csrf_organizer_authority_and_single_address_validation(self):
        url = reverse('activities:send_email_invitation', args=[self.activity.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.host)
        self.assertEqual(secure.post(url, {'email': self.user.email}).status_code, 403)
        self.assertContains(self.client.post(url, {'email': 'a@example.com,b@example.com'}), 'Enter a valid email')
        self.client.force_login(self.wrong)
        self.assertEqual(self.client.post(url, {'email': self.user.email}).status_code, 404)
        self.assertFalse(ActivityEmailInvitation.objects.exists())
        self.client.force_login(self.host)
        self.assertRedirects(self.client.post(url, {'email': self.user.email}), reverse('activities:roster', args=[self.activity.pk]))
        token = re.search(r'/activity-invitations/([^/]+)/', mail.outbox[-1].body).group(1)
        self.assertEqual(secure.post(self.url(token)).status_code, 403)

    def test_group_and_activity_share_unique_recipient_limit(self):
        limits = {**settings.EMAIL_LIMITS, 'invitation_unique_day': 1}
        with override_settings(EMAIL_LIMITS=limits):
            issue_group_invitation(self.group, self.host, 'group-recipient@example.com', self.request)
            with self.assertRaisesRegex(ValidationError, 'daily invitation limit'):
                self.send()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(OutboundEmailAttempt.objects.get(reason='unique_day').activity_reference, self.activity.pk)

    def test_activity_and_group_share_attempt_limit(self):
        limits = {**settings.EMAIL_LIMITS, 'invitation_attempts_day': 1}
        with override_settings(EMAIL_LIMITS=limits):
            self.send()
            with self.assertRaisesRegex(ValidationError, 'daily invitation limit'):
                issue_group_invitation(self.group, self.host, self.user.email, self.request)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(OutboundEmailAttempt.objects.get(reason='attempts_day').group_reference, self.group.pk)

    def test_failed_smtp_retains_quota_backoff_and_dispatches_outside_writer(self):
        def fail(*args, **kwargs):
            self.assertTrue(all(getattr(block, '_from_testcase', False) for block in connection.atomic_blocks))
            return 0
        with patch('belong.email_controls.send_mail', side_effect=fail):
            with self.assertRaisesRegex(ValidationError, 'could not be sent'):
                self.send()
        self.assertEqual(OutboundEmailAttempt.objects.get().outcome, 'failed')
        with self.assertRaisesRegex(ValidationError, 'wait before retrying'):
            self.send()
        with override_settings(EMAIL_LIMITS={**settings.EMAIL_LIMITS, 'invitation_attempts_day': 1}):
            with self.assertRaisesRegex(ValidationError, 'daily invitation limit'):
                self.send('different@example.com')
        self.assertEqual(len(mail.outbox), 0)

    def test_origin_configuration_fails_closed_and_cancelled_activity_cannot_send(self):
        with override_settings(ENVIRONMENT='production', BELONG_PUBLIC_ORIGIN='http://insecure.example'):
            with self.assertRaisesRegex(ValidationError, 'could not be sent'):
                self.send()
        self.assertEqual(OutboundEmailAttempt.objects.get().reason, 'origin_configuration')
        self.activity.status = 'cancelled'
        self.activity.save()
        with self.assertRaisesRegex(ValidationError, 'cancelled'):
            self.send('different@example.com')
        self.assertEqual(len(mail.outbox), 0)

    def test_preexisting_group_consent_is_not_accepted_by_activity_continuation(self):
        issue_group_invitation(self.group, self.host, self.user.email, self.request)
        token = self.send()
        self.client.logout()
        session = self.client.session
        session['pending_group_invitation'] = GroupInvitation.objects.get().pk
        session.save()
        self.client.post(self.url(token), {'auth': 'login'})
        self.client.post(reverse('login'), {'username': self.user.email, 'password': self.password})
        self.assertTrue(ActivityInvitation.objects.filter(user=self.user).exists())
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
