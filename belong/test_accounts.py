import re
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_verification import digest, confirm_email
from social.models import EmailVerification
from media_assets.models import ImageAssetPurpose


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountTests(TestCase):
    password = 'Testing-account-982!'

    def signup(self, email='person@example.com', **kwargs):
        data = {'email': email, 'account_type': 'individual', 'display_name': 'Visible Person', 'password1': self.password, 'password2': self.password, **kwargs}
        return self.client.post(reverse('signup'), data)

    def token(self):
        return re.search(r'/accounts/verify/([^/]+)/', mail.outbox[-1].body).group(1)

    def verified(self):
        self.signup()
        user = get_user_model().objects.get(email='person@example.com')
        self.client.post(reverse('verify_email', args=[self.token()]))
        self.client.post(reverse('account_interests'), {'action': 'skip'})
        return user

    def test_signup_identity_and_gate_all_product_routes(self):
        page = self.client.get(reverse('signup'))
        self.assertNotContains(page, 'name="username"')
        self.assertRedirects(self.signup('Person@EXAMPLE.com', account_type='organization'), reverse('verification_status'))
        user = get_user_model().objects.get(email='person@example.com')
        self.assertTrue(user.username.startswith('u_'))
        self.assertEqual(user.profile.account_type, 'organization')
        self.assertEqual(user.profile.display_name, 'Visible Person')
        self.assertFalse(user.profile.can_use_belong)
        for route in ['activities:index', 'activities:create', 'groups:create', 'account_settings', 'password_change']:
            for method in [self.client.get, self.client.post]:
                with self.subTest(route=route, method=method):
                    self.assertRedirects(method(reverse(route)), reverse('verification_status'))
        response = self.client.post(reverse('activities:create'), HTTP_HX_REQUEST='true')
        self.assertEqual(response['HX-Redirect'], reverse('verification_status'))
        status = self.client.get(reverse('verification_status'))
        self.assertNotContains(status, 'aria-label="Create"')
        self.assertNotContains(status, '>Discover</a>')

    def test_token_digest_post_only_one_time_and_stable_identity(self):
        self.signup()
        user = get_user_model().objects.get(email='person@example.com')
        pk = user.pk
        token = self.token()
        proof = EmailVerification.objects.get()
        self.assertEqual(proof.token_digest, digest(token))
        self.assertNotIn(token, proof.token_digest)
        page = self.client.get(reverse('verify_email', args=[token]))
        self.assertEqual(page['Referrer-Policy'], 'same-origin')
        self.assertContains(page, 'Verify email')
        self.assertFalse(user.profile.can_use_belong)
        self.assertRedirects(self.client.post(reverse('verify_email', args=[token])), reverse('account_interests'))
        user.refresh_from_db()
        self.assertEqual(user.pk, pk)
        self.assertTrue(user.profile.can_use_belong)
        self.assertFalse(user.profile.legacy_access)
        self.assertContains(self.client.post(reverse('verify_email', args=[token])), 'already used')

    def test_expired_token_and_resend_throttle(self):
        self.signup()
        token = self.token()
        self.assertContains(self.client.post(reverse('verification_status'), {'email': 'person@example.com'}), 'Please wait')
        EmailVerification.objects.update(created_at=timezone.now()-timedelta(minutes=2), expires_at=timezone.now()-timedelta(seconds=1))
        self.assertContains(self.client.post(reverse('verify_email', args=[token])), 'expired')
        self.assertRedirects(self.client.post(reverse('verification_status'), {'email': 'person@example.com'}), reverse('verification_status'))
        self.assertNotEqual(self.token(), token)
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_supersedes_old_link_and_daily_limit(self):
        self.signup()
        old = self.token()
        EmailVerification.objects.update(created_at=timezone.now()-timedelta(minutes=2))
        self.client.post(reverse('verification_status'), {'email': 'corrected@example.com'})
        self.assertContains(self.client.post(reverse('verify_email', args=[old])), 'already used')
        self.client.post(reverse('verify_email', args=[self.token()]))
        self.assertTrue(get_user_model().objects.filter(email='corrected@example.com').exists())
        user = get_user_model().objects.get(email='corrected@example.com')
        for i in range(8):
            EmailVerification.objects.create(user=user, email=user.email, token_digest=str(i), created_at=timezone.now()-timedelta(minutes=3), expires_at=timezone.now()+timedelta(hours=1))
        self.assertContains(self.client.post(reverse('account_settings'), {'action': 'email', 'email': 'another@example.com', 'current_password': self.password}), 'Please wait')

    def test_email_login_only_and_local_legacy_escape_hatch(self):
        user = self.verified()
        self.client.logout()
        bad = self.client.post(reverse('login'), {'username': user.username, 'password': self.password})
        self.assertContains(bad, 'correct email and password')
        self.assertRedirects(self.client.post(reverse('login'), {'username': 'PERSON@EXAMPLE.com', 'password': self.password}), reverse('activities:index'))
        self.client.logout()
        from belong.test_helpers import create_legacy_user
        legacy = create_legacy_user('legacy-local', password=self.password)
        with override_settings(ALLOW_LEGACY_ACCOUNTS=False):
            self.assertContains(self.client.post(reverse('login'), {'username': legacy.username, 'password': self.password}), 'correct email and password')
        with override_settings(ALLOW_LEGACY_ACCOUNTS=True):
            self.assertRedirects(self.client.post(reverse('login'), {'username': legacy.username, 'password': self.password}), reverse('activities:index'))

    def test_database_and_signup_enforce_case_insensitive_uniqueness(self):
        get_user_model().objects.create_user('existing', email='Taken@Example.com')
        self.assertContains(self.signup('taken@example.COM'), 'Sign in instead')
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user('duplicate', email='TAKEN@example.com')
        get_user_model().objects.create_user('empty-one')
        get_user_model().objects.create_user('empty-two')

    def test_pending_email_requires_password_and_keeps_old_login_until_confirmation(self):
        user = self.verified()
        pk, username = user.pk, user.username
        EmailVerification.objects.update(created_at=timezone.now()-timedelta(minutes=2))
        wrong = self.client.post(reverse('account_settings'), {'action': 'email', 'email': 'new@example.com', 'current_password': 'wrong'})
        self.assertContains(wrong, 'current password')
        self.assertRedirects(self.client.post(reverse('account_settings'), {'action': 'email', 'email': 'NEW@example.com', 'current_password': self.password}), reverse('account_settings'))
        user.refresh_from_db()
        self.assertEqual(user.email, 'person@example.com')
        self.assertEqual(user.profile.pending_email, 'new@example.com')
        confirm_email(self.token())
        user.refresh_from_db()
        self.assertEqual((user.pk, user.username, user.email), (pk, username, 'new@example.com'))
        self.assertEqual(user.profile.pending_email, '')

    def test_email_claim_race_keeps_old_verified_email(self):
        user = self.verified()
        EmailVerification.objects.update(created_at=timezone.now()-timedelta(minutes=2))
        self.client.post(reverse('account_settings'), {'action': 'email', 'email': 'raced@example.com', 'current_password': self.password})
        token = self.token()
        get_user_model().objects.create_user('winner', email='RACED@example.com')
        self.assertContains(self.client.post(reverse('verify_email', args=[token])), 'no longer available')
        user.refresh_from_db()
        self.assertEqual(user.email, 'person@example.com')
        self.assertTrue(user.profile.can_use_belong)

    def test_delivery_failure_is_retryable_and_does_not_grant_access(self):
        with patch('belong.email_verification.send_mail', side_effect=OSError('test delivery failure')):
            self.assertRedirects(self.signup(), reverse('verification_status'))
        user = get_user_model().objects.get(email='person@example.com')
        self.assertFalse(user.profile.can_use_belong)
        self.assertFalse(EmailVerification.objects.exists())
        self.client.post(reverse('verification_status'), {'email': user.email})
        self.assertEqual(len(mail.outbox), 1)

    def test_profile_avatar_square_metadata_free_and_organization_identity(self):
        user = self.verified()
        source = BytesIO()
        image = Image.new('RGB', (400, 200), 'red')
        image.paste('blue', (200, 0, 400, 200))
        exif = Image.Exif(); exif[274] = 6; exif[270] = 'private metadata'
        image.save(source, format='JPEG', exif=exif)
        upload = SimpleUploadedFile('portrait.not-an-image-extension', source.getvalue(), content_type='text/plain')
        self.assertRedirects(self.client.post(reverse('account_settings'), {'action': 'profile', 'display_name': 'Neighborhood Club', 'account_type': 'organization', 'location': 'Philadelphia 19104', 'avatar': upload}), reverse('account_settings'))
        user.refresh_from_db()
        asset = user.profile.avatar_image
        self.assertEqual(asset.purpose, ImageAssetPurpose.PROFILE_AVATAR)
        with Image.open(BytesIO(bytes(asset.data))) as normalized:
            self.assertEqual(normalized.size, (256, 256))
            self.assertGreater(normalized.getpixel((128, 32))[0], 200)
            self.assertGreater(normalized.getpixel((128, 224))[2], 200)
            self.assertFalse(normalized.getexif())
            self.assertNotIn('icc_profile', normalized.info)
        self.assertEqual(user.profile.location, 'Philadelphia 19104')
        self.assertContains(self.client.get(reverse('activities:index')), 'Neighborhood Club (Organization)')
        self.assertRedirects(self.client.post(reverse('account_settings'), {'action': 'profile', 'display_name': 'Neighborhood Club', 'account_type': 'organization', 'remove_avatar': 'on'}), reverse('account_settings'))
        user.refresh_from_db(); self.assertIsNone(user.profile.avatar_image)

    def test_profile_rejects_fake_and_oversized_images_without_changes(self):
        user = self.verified()
        data = {'action': 'profile', 'display_name': 'Changed', 'account_type': 'individual'}
        for content, message in [(b'not an image', 'valid, non-animated'), (b'x'*(5*1024*1024+1), 'smaller than 5 MB')]:
            response = self.client.post(reverse('account_settings'), {**data, 'avatar': SimpleUploadedFile('fake.png', content)})
            self.assertContains(response, message)
            user.refresh_from_db(); self.assertEqual(user.profile.display_name, 'Visible Person')

    def test_password_change_retains_session_and_new_credentials(self):
        self.verified()
        new_password = 'Replacement-password-927!'
        self.assertRedirects(self.client.post(reverse('password_change'), {'old_password': self.password, 'new_password1': new_password, 'new_password2': new_password}), reverse('password_change_done'))
        self.assertEqual(self.client.get(reverse('account_settings')).status_code, 200)
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('login'), {'username': 'person@example.com', 'password': new_password}), reverse('activities:index'))
