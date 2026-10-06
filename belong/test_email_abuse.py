import os
import re
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from groups.forms import InvitationForm
from groups.invitations import issue_invitation, accept_invitation
from groups.models import Group, GroupInvitation, GroupMembership
from social.models import AccountEmailProof, EmailVerification, OutboundEmailAttempt
from .email_controls import owned_url, address_hash
from .email_verification import send_verification, confirm_email, digest


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='http://testserver')
class EmailAbuseTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('mail-owner', email='owner@example.com', password='Testing-only-817!')
        profile = self.owner.profile
        profile.email_verified_at = timezone.now()
        profile.save()
        self.group = Group.objects.create(name='https://evil.example FREE MONEY\nUntrusted body', owner=self.owner, access='private')
        GroupMembership.objects.create(group=self.group, user=self.owner, role='organizer')
        self.request = RequestFactory().post('/', REMOTE_ADDR='192.0.2.1', HTTP_HOST='evil.example')
        self.client.force_login(self.owner)

    def limits(self, **values):
        return override_settings(EMAIL_LIMITS={**settings.EMAIL_LIMITS, **values})

    def age(self, **filters):
        OutboundEmailAttempt.objects.filter(**filters).update(created_at=timezone.now()-timedelta(minutes=2))

    def token(self, route):
        return re.search('/accounts/'+route+'/([^/]+)/', mail.outbox[-1].body).group(1)

    def setup_data(self):
        return {'display_name': 'Proven Owner', 'account_type': 'organization',
                'password1': 'Owner-chosen-817!', 'password2': 'Owner-chosen-817!'}

    def test_unverified_even_legacy_cannot_send_and_suspension_is_service_enforced(self):
        self.owner.profile.email_verified_at = None
        self.owner.profile.legacy_access = True
        self.owner.profile.save()
        with self.assertRaisesRegex(ValidationError, 'Verify your email'):
            issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(OutboundEmailAttempt.objects.get().reason, 'unverified_account')
        self.owner.profile.email_verified_at = timezone.now()
        self.owner.profile.outbound_mail_suspended = True
        self.owner.profile.save()
        with self.assertRaisesRegex(ValidationError, 'suspended'):
            issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(GroupInvitation.objects.exists())
        self.assertNotContains(self.client.get(self.group.get_absolute_url()), 'Send invitations')
        # Account settings cannot clear the admin-owned switch.
        self.client.post(reverse('account_settings'), {'action': 'profile', 'display_name': 'Owner',
            'account_type': 'organization', 'outbound_mail_suspended': ''})
        self.owner.profile.refresh_from_db()
        self.assertTrue(self.owner.profile.outbound_mail_suspended)

    def test_verified_fixed_content_canonical_origin_and_existing_acceptance(self):
        issue_invitation(self.group, self.owner, 'invitee@example.com', self.request)
        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'Your Belong group invitation')
        self.assertNotIn('evil.example', message.body)
        self.assertNotIn('FREE MONEY', message.body)
        self.assertIn('http://testserver/groups/invitations/', message.body)
        token = re.search(r'/groups/invitations/([^/]+)/', message.body).group(1)
        user = get_user_model().objects.create_user('verified-invitee', email='invitee@example.com')
        user.profile.email_verified_at = timezone.now()
        user.profile.save()
        self.assertEqual(accept_invitation(token, user), self.group)
        self.assertEqual(OutboundEmailAttempt.objects.get().outcome, 'sent')

    def test_batch_defaults_and_settings_limit(self):
        self.assertTrue(InvitationForm({'emails': ','.join(f'p{i}@example.com' for i in range(20))}).is_valid())
        self.assertFalse(InvitationForm({'emails': ','.join(f'p{i}@example.com' for i in range(21))}).is_valid())
        with self.limits(invitation_batch=1):
            self.assertFalse(InvitationForm({'emails': 'one@example.com,two@example.com'}).is_valid())

    def test_rolling_unique_and_total_quotas_same_for_organization(self):
        self.owner.profile.account_type = 'organization'
        self.owner.profile.save()
        with self.limits(invitation_unique_day=2, invitation_attempts_day=3):
            issue_invitation(self.group, self.owner, 'one@example.com', self.request)
            issue_invitation(self.group, self.owner, 'two@example.com', self.request)
            with self.assertRaisesRegex(ValidationError, 'daily invitation limit'):
                issue_invitation(self.group, self.owner, 'three@example.com', self.request)
            other = Group.objects.create(name='Other group', owner=self.owner)
            issue_invitation(other, self.owner, 'one@example.com', self.request)
            another = Group.objects.create(name='Third group', owner=self.owner)
            with self.assertRaisesRegex(ValidationError, 'daily invitation limit'):
                issue_invitation(another, self.owner, 'one@example.com', self.request)
            OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(hours=25))
            issue_invitation(self.group, self.owner, 'three@example.com', self.request)
        self.assertEqual(len(mail.outbox), 4)

    def test_revocation_deletion_retry_and_other_organizer_cannot_reset_cooldown(self):
        issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        token_digest = GroupInvitation.objects.get().token_digest
        GroupInvitation.objects.update(status='revoked')
        with self.assertRaisesRegex(ValidationError, 'seven days'):
            issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(GroupInvitation.objects.get().token_digest, token_digest)
        GroupInvitation.objects.all().delete()
        other = get_user_model().objects.create_user('other-organizer', email='other@example.com')
        other.profile.email_verified_at = timezone.now(); other.profile.save()
        GroupMembership.objects.create(group=self.group, user=other, role='organizer')
        with self.assertRaisesRegex(ValidationError, 'seven days'):
            issue_invitation(self.group, other, 'new@example.com', self.request)
        self.assertEqual(len(mail.outbox), 1)
        OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(days=8))
        issue_invitation(self.group, other, 'new@example.com', self.request)
        self.assertEqual(len(mail.outbox), 2)

    def test_failed_invitation_consumes_quota_and_explicit_retry_is_delayed(self):
        with patch('belong.email_controls.send_mail', side_effect=OSError('sensitive provider detail')):
            with self.assertRaisesRegex(ValidationError, 'could not be sent'):
                issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(OutboundEmailAttempt.objects.get().outcome, 'failed')
        self.assertNotIn('sensitive', OutboundEmailAttempt.objects.get().reason)
        with self.assertRaisesRegex(ValidationError, 'wait'):
            issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(minutes=6))
        issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(len(mail.outbox), 1)

    def test_signup_and_recovery_have_same_response_and_cookie_surfaces(self):
        self.client.logout()
        for route in ['signup', 'password_reset']:
            existing = Client()
            unknown = Client()
            # Normalize the random CSRF value to compare the entire resulting HTML.
            a = existing.post(reverse(route), {'email': self.owner.email}, follow=True)
            b = unknown.post(reverse(route), {'email': f'{route}-unknown@example.com'}, follow=True)
            self.assertEqual(a.redirect_chain, b.redirect_chain)
            self.assertEqual(a.status_code, b.status_code)
            normalized = lambda response: re.sub(r'value="[A-Za-z0-9]{64}"', 'value="CSRF"', response.content.decode())
            self.assertEqual(normalized(a), normalized(b))
            self.assertEqual(set(a.cookies), set(b.cookies))
            self.assertNotIn(settings.SESSION_COOKIE_NAME, a.cookies)
            self.assertNotIn(settings.SESSION_COOKIE_NAME, b.cookies)
        self.assertFalse(get_user_model().objects.filter(email='signup-unknown@example.com').exists())

    def test_signup_ip_attempt_hour_day_and_address_throttles_are_durable(self):
        self.client.logout()
        with self.limits(signup_ip_hour=2, signup_ip_day=3):
            for i in range(3):
                self.client.post(reverse('signup'), {'email': f'signup{i}@example.com'})
            self.assertEqual(len(mail.outbox), 2)
            self.age()
            OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(hours=2))
            self.client.post(reverse('signup'), {'email': 'third@example.com'})
            self.client.post(reverse('signup'), {'email': 'fourth@example.com'})
            self.assertEqual(len(mail.outbox), 3)
            self.assertEqual(OutboundEmailAttempt.objects.filter(reason='signup_ip_day').count(), 1)
        self.assertEqual(OutboundEmailAttempt.objects.count(), 5)
        self.assertFalse(get_user_model().objects.filter(username__startswith='u_').exists())

    def test_verification_and_recovery_share_address_ip_limits_and_own_address_rule(self):
        # Three actual sends; requests/cooldowns remain journaled independently of tokens.
        for _ in range(3):
            send_verification(self.request, self.owner, self.owner.email)
            self.age()
        with self.assertRaisesRegex(ValidationError, 'Please wait'):
            send_verification(self.request, self.owner, self.owner.email)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(OutboundEmailAttempt.objects.filter(outcome='blocked').count(), 1)
        self.client.logout()
        self.client.post(reverse('password_reset'), {'email': self.owner.email}, REMOTE_ADDR='192.0.2.1')
        self.assertEqual(len(mail.outbox), 3)
        self.owner.profile.email_verified_at = None; self.owner.profile.save()
        with self.assertRaises(ValidationError):
            send_verification(self.request, self.owner, 'someone-else@example.com')
        with self.limits(own_ip_hour=1):
            self.client.post(reverse('password_reset'), {'email': 'new-recipient@example.com'}, REMOTE_ADDR='192.0.2.1')
        self.assertEqual(len(mail.outbox), 3)

    def test_preclaim_replaced_only_by_owner_proof_and_old_sessions_invalidated(self):
        provisional = get_user_model().objects.create_user('attacker-provisional', email='preclaim@example.com', password='Attacker-password-817!')
        provisional.profile.display_name = 'Attacker profile'; provisional.profile.save()
        attacker = Client(); attacker.force_login(provisional)
        self.client.logout()
        self.client.post(reverse('signup'), {'email': provisional.email, 'password1': 'Unauthenticated-overwrite!'})
        provisional.refresh_from_db()
        self.assertTrue(provisional.check_password('Attacker-password-817!'))
        token = self.token('setup')
        self.assertEqual(self.client.get(reverse('complete_signup', args=[token])).status_code, 200)
        provisional.refresh_from_db(); self.assertFalse(provisional.profile.email_verified_at)
        self.assertRedirects(self.client.post(reverse('complete_signup', args=[token]), self.setup_data()), reverse('account_interests'))
        provisional.refresh_from_db()
        self.assertTrue(provisional.check_password('Owner-chosen-817!'))
        self.assertEqual(provisional.profile.display_name, 'Proven Owner')
        self.assertEqual(provisional.profile.account_type, 'organization')
        self.assertEqual(attacker.get(reverse('account_settings')).status_code, 302)
        self.assertContains(self.client.get(reverse('complete_signup', args=[token])), 'already used')

    def test_old_provisional_verification_link_cannot_activate_attacker_password(self):
        provisional = get_user_model().objects.create_user('old-provisional', email='old@example.com', password='Attacker-password-817!')
        provisional.profile.pending_email = provisional.email; provisional.profile.save()
        EmailVerification.objects.create(user=provisional, email=provisional.email, token_digest=digest('old-link'), expires_at=timezone.now()+timedelta(hours=1))
        with self.assertRaisesRegex(ValidationError, 'setup link'):
            confirm_email('old-link')
        provisional.profile.refresh_from_db(); self.assertFalse(provisional.profile.can_use_belong)

    def test_recovery_proof_post_only_expiring_one_time_and_no_automatic_login(self):
        original_session = Client(); original_session.force_login(self.owner)
        self.client.logout()
        self.client.post(reverse('password_reset'), {'email': self.owner.email})
        token = self.token('recover')
        proof = AccountEmailProof.objects.get(purpose='recovery')
        self.assertEqual(proof.token_digest, digest(token))
        self.client.get(reverse('complete_recovery', args=[token]))
        self.owner.refresh_from_db(); self.assertTrue(self.owner.check_password('Testing-only-817!'))
        self.assertRedirects(self.client.post(reverse('complete_recovery', args=[token]), {
            'new_password1': 'Recovered-password-817!', 'new_password2': 'Recovered-password-817!'}), reverse('login'))
        self.owner.refresh_from_db(); self.assertTrue(self.owner.check_password('Recovered-password-817!'))
        self.assertContains(self.client.get(reverse('complete_recovery', args=[token])), 'already used')
        self.assertEqual(original_session.get(reverse('account_settings')).status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_successful_account_creation_quota_at_completion(self):
        from .account_email import complete_signup
        with self.limits(creation_ip_hour=1):
            for i in range(2):
                AccountEmailProof.objects.create(email=f'create{i}@example.com', purpose='signup', token_digest=digest(f'proof{i}'), expires_at=timezone.now()+timedelta(hours=1))
            user = complete_signup(self.request, 'proof0', self.setup_data())
            self.assertTrue(user.profile.email_verified_at)
            with self.assertRaisesRegex(ValidationError, 'wait'):
                complete_signup(self.request, 'proof1', self.setup_data())
            self.assertFalse(get_user_model().objects.filter(email='create1@example.com').exists())
            OutboundEmailAttempt.objects.filter(kind='account_creation').update(created_at=timezone.now()-timedelta(hours=2))
            complete_signup(self.request, 'proof1', self.setup_data())


    def test_recovery_of_provisional_address_requires_owner_identity_and_password(self):
        provisional = get_user_model().objects.create_user('preclaimed-recovery', email='preclaimed-recovery@example.com', password='Attacker-password-817!')
        self.client.logout()
        self.client.post(reverse('password_reset'), {'email': provisional.email})
        proof = AccountEmailProof.objects.get(email=provisional.email)
        self.assertEqual(proof.purpose, 'signup')
        token = self.token('setup')
        self.assertContains(self.client.post(reverse('complete_signup', args=[token]), {}), 'This field is required')
        provisional.refresh_from_db(); self.assertFalse(provisional.profile.email_verified_at)
        self.assertRedirects(self.client.post(reverse('complete_signup', args=[token]), self.setup_data()), reverse('account_interests'))
        provisional.refresh_from_db()
        self.assertEqual(provisional.profile.display_name, 'Proven Owner')
        self.assertTrue(provisional.check_password('Owner-chosen-817!'))

    def test_daily_creation_ceiling_and_recovery_expiry(self):
        from .account_email import complete_signup
        with self.limits(creation_ip_day=1):
            for i in range(2):
                AccountEmailProof.objects.create(email=f'daily{i}@example.com', purpose='signup', token_digest=digest(f'daily{i}'), expires_at=timezone.now()+timedelta(hours=24))
            complete_signup(self.request, 'daily0', self.setup_data())
            OutboundEmailAttempt.objects.filter(kind='account_creation').update(created_at=timezone.now()-timedelta(hours=2))
            with self.assertRaises(ValidationError): complete_signup(self.request, 'daily1', self.setup_data())
            OutboundEmailAttempt.objects.filter(kind='account_creation').update(created_at=timezone.now()-timedelta(hours=25))
            complete_signup(self.request, 'daily1', self.setup_data())
        self.client.logout()
        self.client.post(reverse('password_reset'), {'email': self.owner.email})
        token = self.token('recover')
        AccountEmailProof.objects.filter(purpose='recovery').update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertContains(self.client.post(reverse('complete_recovery', args=[token]), {'new_password1': 'Not-used-817!', 'new_password2': 'Not-used-817!'}), 'expired')
        self.owner.refresh_from_db(); self.assertTrue(self.owner.check_password('Testing-only-817!'))

    def test_suspension_covers_email_changes_and_inactive_accounts_cannot_send(self):
        self.owner.profile.outbound_mail_suspended = True; self.owner.profile.save()
        with self.assertRaisesRegex(ValidationError, 'suspended'):
            send_verification(self.request, self.owner, 'third-party@example.com')
        send_verification(self.request, self.owner, self.owner.email)
        self.assertEqual(len(mail.outbox), 1)
        self.owner.is_active = False; self.owner.save()
        with self.assertRaisesRegex(ValidationError, 'cannot send'):
            issue_invitation(self.group, self.owner, 'new@example.com', self.request)
        self.assertEqual(len(mail.outbox), 1)


class EmailOriginTests(SimpleTestCase):
    def test_production_origin_fails_closed_without_valid_https_origin(self):
        with override_settings(ENVIRONMENT='production'):
            for origin in ['', 'http://belong.example', 'https://belong.example/evil', 'https://name:password@belong.example', 'https://belong.example/?x=1']:
                with self.subTest(origin=origin), override_settings(BELONG_PUBLIC_ORIGIN=origin):
                    with self.assertRaises(ImproperlyConfigured): owned_url('signup')
            with override_settings(BELONG_PUBLIC_ORIGIN='https://belong.example'):
                self.assertEqual(owned_url('signup'), 'https://belong.example/accounts/signup/')

    def test_file_backed_concurrent_quota_reservations_and_smtp_outside_lock(self):
        with tempfile.TemporaryDirectory() as root:
            env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'belong.settings', 'BELONG_ENV': 'test',
                'BELONG_PUBLIC_ORIGIN': 'http://testserver', 'DJANGO_DB_PATH': str(Path(root)/'concurrency.sqlite3')}
            code = '''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections, connection
from django.test import RequestFactory
from django.utils import timezone
from groups.models import Group, GroupMembership
from groups.invitations import issue_invitation
from social.models import OutboundEmailAttempt, AccountEmailProof
from belong.email_verification import digest
from belong.account_email import complete_signup
call_command('migrate', verbosity=0)
u = get_user_model().objects.create_user('quota-owner', email='owner@example.com')
u.profile.email_verified_at = timezone.now(); u.profile.save()
g = Group.objects.create(name='Quota group', owner=u)
GroupMembership.objects.create(group=g, user=u, role='organizer')
settings.EMAIL_LIMITS = {**settings.EMAIL_LIMITS, 'invitation_unique_day': 1, 'invitation_attempts_day': 1, 'creation_ip_hour': 1}
barrier = Barrier(2)
def send(subject, body, sender, recipients, **kwargs):
    assert not connection.in_atomic_block, 'SMTP held a transaction'
    return 1
def invite(i):
    barrier.wait(timeout=10)
    try:
        issue_invitation(g, u, f'p{i}@example.com', RequestFactory().post('/'))
        return 'sent'
    except ValidationError:
        return 'limited'
    finally:
        connections.close_all()
with patch('belong.email_controls.send_mail', side_effect=send):
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(invite, range(2)))
assert sorted(outcomes) == ['limited', 'sent'], outcomes
assert OutboundEmailAttempt.objects.filter(kind='invitation', outcome='sent').count() == 1
for i in range(2):
    AccountEmailProof.objects.create(email=f'new{i}@example.com', purpose='signup', token_digest=digest(f'proof{i}'), expires_at=timezone.now()+timedelta(hours=1))
barrier = Barrier(2)
def create(i):
    barrier.wait(timeout=10)
    try:
        complete_signup(RequestFactory().post('/'), f'proof{i}', {'display_name':'Owner','account_type':'individual','password1':'Only-for-test-817!'})
        return 'created'
    except ValidationError:
        return 'limited'
    finally:
        connections.close_all()
with ThreadPoolExecutor(max_workers=2) as pool:
    outcomes = list(pool.map(create, range(2)))
assert sorted(outcomes) == ['created', 'limited'], outcomes
assert OutboundEmailAttempt.objects.filter(kind='account_creation', outcome='created').count() == 1
'''
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
