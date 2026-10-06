from belong.test_helpers import create_legacy_user
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone

from .invitations import issue_invitation, accept_invitation, digest
from .models import Group, GroupInvitation, GroupMembership


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InvitationTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.owner = create_legacy_user('janine', email='janine@example.com', password='Testing-only-817!')
        self.user = create_legacy_user('invitee', email='hiker@example.com', password='Testing-only-817!')
        self.wrong = create_legacy_user('wrong', email='other@example.com')
        self.group = Group.objects.create(name='Private hikes', description='Secret trails', owner=self.owner, access='private')
        GroupMembership.objects.create(group=self.group, user=self.owner, role='organizer')
        self.owner.profile.email_verified_at = timezone.now()
        self.owner.profile.save()
        self.wrong.profile.email_verified_at = timezone.now()
        self.wrong.profile.save()
        self.client.force_login(self.owner)

    def send(self, email='hiker@example.com'):
        response = self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': email})
        self.assertEqual(response.status_code, 302)
        return mail.outbox[-1].body.split('Review and accept: ')[1].split('\n')[0].split('/')[-2]

    def url(self, token):
        return reverse('groups:invitation', args=[token])

    def test_secure_email_delivery_and_duplicate_cooldown(self):
        token = self.send('HIKER@example.com, hiker@example.com')
        invite = GroupInvitation.objects.get()
        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(invite.token_digest, digest(token))
        self.assertEqual(invite.email, 'hiker@example.com')
        self.assertEqual(mail.outbox[0].to, ['hiker@example.com'])
        self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': self.user.email})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(GroupInvitation.objects.get().token_digest, digest(token))
        self.assertNotContains(self.client.get(self.group.get_absolute_url()), token)

    def age_mail(self):
        from social.models import OutboundEmailAttempt
        OutboundEmailAttempt.objects.update(created_at=timezone.now()-timedelta(days=8))

    def test_all_modes_invitation_is_approval_and_idempotent(self):
        for access in ['open', 'closed', 'unlisted', 'private']:
            with self.subTest(access=access):
                self.group.access = access; self.group.save()
                token = self.send()
                self.client.force_login(self.user)
                self.assertEqual(self.client.get(self.url(token)).status_code, 200)
                self.assertFalse(self.group.memberships.filter(user=self.user).exists())
                for _ in range(2):
                    self.assertRedirects(self.client.post(self.url(token)), self.group.get_absolute_url())
                self.assertEqual(self.group.memberships.filter(user=self.user, status='active').count(), 1)
                self.group.memberships.filter(user=self.user).delete()
                self.client.post(self.url(token))
                self.assertFalse(self.group.memberships.filter(user=self.user).exists())
                self.client.force_login(self.owner)
                self.age_mail()

    def test_private_identity_valid_bearer_only_and_wrong_account_cannot_accept(self):
        token = self.send()
        self.client.logout()
        self.assertContains(self.client.get(self.url(token)), 'Secret trails')
        self.assertEqual(self.client.get(self.url(token))['Referrer-Policy'], 'same-origin')
        self.client.force_login(self.wrong)
        self.assertNotContains(self.client.get(self.url(token)), 'Secret trails')
        self.client.post(self.url(token))
        self.assertFalse(self.group.memberships.filter(user=self.wrong).exists())
        self.assertEqual(self.client.get(self.group.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(self.url('tampered')), self.group.name)

    def test_login_continuation_and_wrong_user_retry(self):
        token = self.send()
        self.client.logout()
        self.assertRedirects(self.client.post(self.url(token), {'auth': 'login'}), reverse('login'))
        self.assertIn('pending_group_invitation', self.client.session)
        response = self.client.post(reverse('login'), {'username': 'janine@example.com', 'password': 'Testing-only-817!'})
        self.assertRedirects(response, reverse('groups:pending_invitation'))
        self.assertIn('pending_group_invitation', self.client.session)
        self.client.post(self.url(token), {'auth': 'switch'})
        response = self.client.post(reverse('login'), {'username': 'hiker@example.com', 'password': 'Testing-only-817!'})
        self.assertRedirects(response, self.group.get_absolute_url())
        self.assertNotIn('pending_group_invitation', self.client.session)

    def test_signup_preserves_invitation_through_errors_and_rejects_changed_email(self):
        token = self.send('new@example.com')
        self.client.logout()
        self.client.post(self.url(token), {'auth': 'signup'})
        page = self.client.get(reverse('signup'))
        self.assertContains(page, 'value="new@example.com"')
        data = {'account_type': 'individual', 'display_name': 'New Hiker', 'email': 'other@example.com', 'password1': 'Testing-only-817!', 'password2': 'Testing-only-817!'}
        self.assertContains(self.client.post(reverse('signup'), data), 'Use the invited email')
        self.assertFalse(get_user_model().objects.filter(username='new-hiker').exists())
        data['email'] = 'NEW@example.com'
        self.assertRedirects(self.client.post(reverse('signup'), data), reverse('account_email_requested'))
        self.assertIn('pending_group_invitation', self.client.session)
        from belong.email_verification import digest
        from social.models import AccountEmailProof
        import re
        from django.core import mail
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        self.assertTrue(AccountEmailProof.objects.filter(token_digest=digest(proof)).exists())
        self.assertRedirects(self.client.post(reverse('complete_signup', args=[proof]), data), reverse('account_interests'))
        user = get_user_model().objects.get(email='new@example.com')
        self.assertRedirects(self.client.post(reverse('account_interests'), {'action': 'skip'}), self.group.get_absolute_url())
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(self.group.memberships.filter(user=user, status='active').exists())

    def test_invitation_finishes_after_cross_browser_setup_and_original_browser_login(self):
        import re
        token = self.send('cross-browser@example.com')
        self.client.logout()
        self.client.post(self.url(token), {'auth': 'signup'})
        self.client.post(reverse('signup'), {'email': 'cross-browser@example.com'})
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        other_browser = Client()
        data = {'account_type': 'individual', 'display_name': 'Cross Browser',
                'password1': 'Testing-only-817!', 'password2': 'Testing-only-817!'}
        self.assertRedirects(other_browser.post(reverse('complete_signup', args=[proof]), data), reverse('account_interests'))
        user = get_user_model().objects.get(email='cross-browser@example.com')
        self.assertFalse(self.group.memberships.filter(user=user).exists())
        self.assertRedirects(self.client.post(reverse('login'), {'username': user.email, 'password': data['password1']}), reverse('account_interests'))
        self.assertTrue(self.group.memberships.filter(user=user, status='active').exists())
        self.assertNotIn('pending_group_invitation', self.client.session)
        self.assertRedirects(self.client.post(reverse('account_interests'), {'interests': []}), self.group.get_absolute_url())

    def test_unverified_invitee_keeps_nonsecret_reference_until_verification(self):
        import re
        from django.core import mail
        from django.contrib.sessions.models import Session
        token = self.send()
        self.user.profile.legacy_access = False
        self.user.profile.email_verified_at = None
        self.user.profile.save()
        self.client.force_login(self.user)
        page = self.client.get(self.url(token))
        self.assertContains(page, 'Verify email and accept')
        self.assertRedirects(self.client.post(self.url(token)), reverse('verification_status'))
        session = self.client.session
        self.assertEqual(session['pending_group_invitation'], GroupInvitation.objects.get().pk)
        self.assertNotIn('group_invitation', session)
        decoded = Session.objects.get(session_key=session.session_key).get_decoded()
        self.assertNotIn(token, str(decoded))
        self.assertFalse(self.group.memberships.filter(user=self.user, status='active').exists())
        self.client.post(reverse('verification_status'), {'email': self.user.email})
        proof = re.search(r'/accounts/setup/([^/]+)/', mail.outbox[-1].body).group(1)
        data = {'account_type': 'individual', 'display_name': 'Owner', 'password1': 'Testing-only-817!', 'password2': 'Testing-only-817!'}
        self.assertRedirects(self.client.post(reverse('complete_signup', args=[proof]), data), reverse('account_interests'))
        self.assertRedirects(self.client.post(reverse('account_interests'), {'action': 'skip'}), self.group.get_absolute_url())
        self.assertTrue(self.group.memberships.filter(user=self.user, status='active').exists())

    def test_existing_email_signup_requires_login(self):
        token = self.send(); self.client.logout()
        self.client.post(self.url(token), {'auth': 'signup'})
        page = self.client.post(reverse('signup'), {'username': 'duplicate', 'email': self.user.email,
                                'password1': 'Testing-only-817!', 'password2': 'Testing-only-817!'})
        self.assertRedirects(page, reverse('account_email_requested'))
        self.assertFalse(get_user_model().objects.filter(username='duplicate').exists())

    def test_expiry_revocation_block_and_pending_membership(self):
        token = self.send()
        invite = GroupInvitation.objects.get()
        invite.expires_at = timezone.now() - timedelta(seconds=1); invite.save()
        with self.assertRaises(ValidationError): accept_invitation(token, self.user)
        self.age_mail()
        token = self.send()
        self.client.post(reverse('groups:revoke_invitation', args=[self.group.pk, invite.pk]))
        with self.assertRaises(ValidationError): accept_invitation(token, self.user)
        self.age_mail()
        token = self.send()
        member = GroupMembership.objects.create(group=self.group, user=self.user, status='blocked')
        with self.assertRaises(ValidationError): accept_invitation(token, self.user)
        member.status = 'pending'; member.save()
        accept_invitation(token, self.user)
        member.refresh_from_db(); self.assertEqual(member.status, 'active')

    def test_authority_distinct_from_access_and_post_csrf(self):
        for access in ['open', 'closed', 'unlisted', 'private']:
            self.group.access = access; self.group.save()
            self.client.force_login(self.wrong)
            self.assertEqual(self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': 'new@example.com'}).status_code, 404)
        member = GroupMembership.objects.create(group=self.group, user=self.wrong, role='organizer')
        self.assertEqual(self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': 'new@example.com'}).status_code, 302)
        invite = GroupInvitation.objects.get()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('groups:revoke_invitation', args=[self.group.pk, invite.pk])).status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf.post(self.url('invalid')).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('groups:invite', args=[self.group.pk])).status_code, 405)

    def test_invalid_batch_and_delivery_failure_have_durable_bounded_retry(self):
        self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': 'valid@example.com invalid'})
        self.assertEqual(GroupInvitation.objects.count(), 0)
        with patch('belong.email_controls.send_mail', side_effect=OSError('test delivery failure')):
            self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': self.user.email})
        from social.models import OutboundEmailAttempt
        self.assertEqual(OutboundEmailAttempt.objects.get().outcome, 'failed')
        self.assertEqual(GroupInvitation.objects.count(), 1)
        self.client.post(reverse('groups:invite', args=[self.group.pk]), {'emails': self.user.email})
        self.assertEqual(len(mail.outbox), 0)
        self.age_mail()
        self.send()
        self.assertEqual(len(mail.outbox), 1)

    def test_legacy_blank_email_binds_only_on_explicit_acceptance(self):
        legacy = create_legacy_user('legacy-signup')
        token = self.send('legacy@example.com')
        self.client.force_login(legacy)
        page = self.client.get(self.url(token))
        self.assertContains(page, 'Accepting will add legacy@example.com to your account')
        legacy.refresh_from_db()
        self.assertEqual(legacy.email, '')
        self.assertFalse(self.group.memberships.filter(user=legacy).exists())
        self.assertEqual(self.client.get(self.group.get_absolute_url()).status_code, 404)
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url(token)), self.group.get_absolute_url())
        legacy.refresh_from_db()
        self.assertEqual(legacy.email, 'legacy@example.com')
        self.assertEqual(self.group.memberships.filter(user=legacy, status='active').count(), 1)
        self.assertEqual(GroupInvitation.objects.get().accepted_by, legacy)

    def test_blank_email_login_binds_from_prior_explicit_acceptance(self):
        legacy = create_legacy_user('legacy-login', password='Testing-only-817!')
        token = self.send('legacy@example.com')
        self.client.logout()
        # Following a link/login alone is not acceptance.
        self.client.get(self.url(token))
        self.client.post(reverse('login'), {'username': legacy.username, 'password': 'Testing-only-817!'})
        legacy.refresh_from_db(); self.assertEqual(legacy.email, '')
        self.client.post(reverse('logout'))
        self.client.post(self.url(token), {'auth': 'login'})
        response = self.client.post(reverse('login'), {'username': legacy.username, 'password': 'Testing-only-817!'})
        self.assertRedirects(response, self.group.get_absolute_url())
        legacy.refresh_from_db(); self.assertEqual(legacy.email, 'legacy@example.com')

    def test_blank_email_conflict_does_not_bind_or_join(self):
        legacy = create_legacy_user('legacy-conflict')
        self.user.email = 'HIKER@EXAMPLE.COM'; self.user.save()
        token = self.send()
        self.client.force_login(legacy)
        page = self.client.post(self.url(token))
        self.assertContains(page, 'Another account already uses the invited email address')
        self.assertNotContains(page, 'Secret trails')
        legacy.refresh_from_db(); self.assertEqual(legacy.email, '')
        self.assertFalse(self.group.memberships.filter(user=legacy).exists())
        self.assertEqual(GroupInvitation.objects.get().status, 'pending')

    def test_invalid_or_blocked_invitation_cannot_bind_blank_email(self):
        legacy = create_legacy_user('legacy-invalid')
        token = self.send('legacy@example.com')
        invite = GroupInvitation.objects.get()
        for status in ['revoked', 'accepted']:
            invite.status = status; invite.save()
            with self.assertRaises(ValidationError): accept_invitation(token, legacy)
        invite.status = 'pending'; invite.expires_at = timezone.now() - timedelta(seconds=1); invite.save()
        with self.assertRaises(ValidationError): accept_invitation(token, legacy)
        invite.expires_at = timezone.now() + timedelta(days=1); invite.save()
        GroupMembership.objects.create(group=self.group, user=legacy, status='blocked')
        with self.assertRaises(ValidationError): accept_invitation(token, legacy)
        legacy.refresh_from_db(); self.assertEqual(legacy.email, '')
        self.assertEqual(self.group.memberships.get(user=legacy).status, 'blocked')

    def test_nonblank_email_is_never_overwritten_and_stale_user_is_reread(self):
        legacy = create_legacy_user('stale-email')
        token = self.send('legacy@example.com')
        get_user_model().objects.filter(pk=legacy.pk).update(email='different@example.com')
        with self.assertRaises(ValidationError): accept_invitation(token, legacy)
        legacy.refresh_from_db(); self.assertEqual(legacy.email, 'different@example.com')
        self.assertFalse(self.group.memberships.filter(user=legacy).exists())
