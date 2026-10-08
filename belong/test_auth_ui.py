from belong.test_helpers import create_legacy_user
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AuthScreenTests(TestCase):
    def test_signed_out_headers_show_only_identity_and_auth_links_stay_in_panels(self):
        for page, action, label in [("login", "signup", "Create account"), ("signup", "login", "Sign in")]:
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertEqual(response.status_code, 200)
                header = response.content.decode().split("<header", 1)[1].split("</header>", 1)[0]
                self.assertNotIn(label, header)
                self.assertEqual(header.count("<a "), 1)
                panel = response.content.decode().split('<section', 1)[1].split('</section>', 1)[0]
                self.assertIn(f'href="{reverse(action)}"', panel)
                self.assertIn(label, panel)
                for text in ["Discover", "Categories", "Create Activity", "Logout", "data-menu-toggle", "primary-navigation"]:
                    self.assertNotIn(text, header)
                for route in ["activities:index", "activities:categories", "activities:create", "logout"]:
                    self.assertNotIn(f'href="{reverse(route)}"', header)
                self.assertContains(response, '<img', count=1)
                self.assertContains(response, 'id="auth-heading"')
                self.assertNotContains(response, "bg-gradient")

    def test_login_uses_requested_functional_copy(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Welcome back.")
        self.assertContains(response, "See what’s happening, find something to do, or put something out there.")
        self.assertContains(response, '>Sign in</button>')
        self.assertContains(response, '>Sign in</h2>')
        for phrase in ["your people", "conversations", "feed", "curated", "circles", "celebrate wins", "community-led", "reconnect", "Belong login", "Enter Belong"]:
            self.assertNotIn(phrase.lower(), response.content.decode().lower())

    def test_login_errors_and_next_destination_still_work(self):
        destination = reverse("activities:create")
        response = self.client.post(reverse("login"), {"username": "unknown", "password": "incorrect", "next": destination})
        self.assertContains(response, "Please enter a correct email and password")
        self.assertContains(response, f'name="next" value="{destination}"')
        create_legacy_user(username="auth-review", password="test-only-password-13")
        response = self.client.post(reverse("login"), {"username": "auth-review", "password": "test-only-password-13", "next": destination})
        self.assertRedirects(response, destination)

    def test_signup_validation_remains_visible_without_creating_an_account(self):
        response = self.client.post(reverse("signup"), {"username": "new-reviewer", "password1": "short", "password2": "different"})
        self.assertContains(response, "This field is required.")
        self.assertFalse(get_user_model().objects.filter(username="new-reviewer").exists())

    def test_authenticated_product_navigation_is_retained(self):
        user = create_legacy_user(username="navigation-review")
        self.client.force_login(user)
        response = self.client.get(reverse("activities:index"))
        header = response.content.decode().split("<header", 1)[1].split("</header>", 1)[0]
        primary = header.split("<details", 1)[0]
        self.assertIn("Discover", primary)
        self.assertNotIn(">Create</a>", primary)
        self.assertContains(response, 'aria-label="Create"')
        self.assertContains(response, f'href="{reverse("groups:create")}"')
        self.assertNotIn("Logout", primary)
        self.assertNotIn("Categories", header)
        account = header.split("<details", 1)[1]
        self.assertIn("Logout", account)
        self.assertIn('method="post"', account)
        self.assertIn('name="csrfmiddlewaretoken"', account)
        self.assertIn(user.username, account)

    def test_normal_signup_requires_persists_and_normalizes_email(self):
        page = self.client.get(reverse('signup'))
        self.assertContains(page, 'name="email"')
        data = {'account_type': 'individual', 'display_name': 'New Person', 'password1': 'Testing-normal-817!', 'password2': 'Testing-normal-817!'}
        self.assertContains(self.client.post(reverse('signup'), data), 'This field is required')
        self.assertFalse(get_user_model().objects.filter(username='ordinary-signup').exists())
        data['email'] = 'New.Person@EXAMPLE.com'
        self.assertRedirects(self.client.post(reverse('signup'), data), reverse('account_email_requested'))
        self.assertFalse(get_user_model().objects.filter(email='new.person@example.com').exists())
        from social.models import AccountEmailProof
        self.assertEqual(AccountEmailProof.objects.get().email, 'new.person@example.com')

    def test_normal_signup_rejects_email_already_claimed_case_insensitively(self):
        create_legacy_user('existing-email', email='Existing@Example.com')
        response = self.client.post(reverse('signup'), {'username': 'duplicate-email', 'email': 'existing@example.COM',
                                    'password1': 'Testing-normal-817!', 'password2': 'Testing-normal-817!'})
        self.assertRedirects(response, reverse('account_email_requested'))
        self.assertFalse(get_user_model().objects.filter(username='duplicate-email').exists())


class HeaderIdentityTests(TestCase):
    def setUp(self):
        self.user = create_legacy_user(username='identity-user', first_name='Full', last_name='Name')
        self.client.force_login(self.user)

    def header(self, route='activities:index'):
        response = self.client.get(reverse(route))
        self.assertEqual(response.status_code, 200)
        return response.content.decode().split('<header', 1)[1].split('</header>', 1)[0]

    def test_display_name_and_organization_identity_replace_generic_trigger(self):
        profile = self.user.profile
        profile.display_name = 'Neighborhood Club'
        profile.account_type = 'organization'
        profile.save()
        header = self.header()
        trigger = header.split('<summary', 1)[1].split('</summary>', 1)[0]
        self.assertIn('Neighborhood Club (Organization): account menu', trigger)
        self.assertIn('>NC</span>', trigger)
        self.assertNotIn('>Menu<', trigger)
        self.assertNotIn('>Account<', trigger)
        self.assertIn(reverse('account_settings'), header)
        self.assertIn('method="post"', header)
        self.assertIn('csrfmiddlewaretoken', header)

    def test_dropdown_has_only_peer_account_rows_without_repeated_identity(self):
        header = self.header()
        account = header.split('<details', 1)[1].split('</details>', 1)[0]
        trigger, panel = account.split('</summary>', 1)
        self.assertIn('class="ui-identity-trigger"', trigger)
        self.assertNotIn('ui-menu-trigger', trigger)
        self.assertNotIn(self.user.profile.identity_label, panel)
        self.assertEqual(panel.count('class="ui-account-menu__item"'), 3)
        self.assertIn(reverse('activities:history'), panel)
        self.assertEqual(panel.count('<a '), 2)
        self.assertEqual(panel.count('<button '), 1)
        self.assertIn('Account settings', panel)
        self.assertIn('Logout', panel)
        self.assertNotIn('Discover', panel)
        self.assertNotIn('ui-button', panel)
        self.assertIn('aria-label="Belong · Discover"', header)
        self.assertIn('href="'+reverse('activities:index')+'" class="ui-brand"', header)

    def test_menu_logout_keeps_post_and_csrf_protection(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.get(reverse('logout')).status_code, 405)
        self.assertEqual(secure.post(reverse('logout')).status_code, 403)
        secure.get(reverse('activities:index'))
        from django.conf import settings
        csrf = secure.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertRedirects(secure.post(reverse('logout'), {'csrfmiddlewaretoken': csrf}),
                             reverse(settings.LOGOUT_REDIRECT_URL), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', secure.session)

    def test_avatar_is_used_when_present(self):
        from media_assets.models import ImageAsset, ImageAssetPurpose
        asset = ImageAsset.objects.create(name='avatar', purpose=ImageAssetPurpose.PROFILE_AVATAR,
                                         data=b'fixture', content_type='image/png', size=7)
        self.user.profile.avatar_image = asset
        self.user.profile.save()
        header = self.header()
        self.assertIn(f'src="{asset.get_absolute_url()}" alt=""', header)
        self.assertNotIn('ui-identity-avatar--fallback', header)

    def test_full_name_then_username_fallback(self):
        profile = self.user.profile
        profile.display_name = ''
        profile.save()
        self.assertIn('Full Name: account menu', self.header())
        self.assertIn('>FN</span>', self.header())
        self.user.first_name = self.user.last_name = ''
        self.user.save()
        self.assertIn('identity-user: account menu', self.header())
        self.assertIn('>I</span>', self.header())

    def test_missing_profile_has_identity_fallback_without_granting_access(self):
        self.user.profile.delete()
        self.assertRedirects(self.client.get(reverse('activities:index')), reverse('verification_status'))
        header = self.header('verification_status')
        self.assertIn('Full Name: account menu', header)
        self.assertIn('>FN</span>', header)
        self.assertIn('Verify email', header)
        self.assertNotIn('Account settings', header)
        self.assertNotIn('>Discover</a>', header)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.can_use_belong)
        self.assertFalse(self.user.profile.legacy_access)
        self.assertIsNone(self.user.profile.email_verified_at)

    def test_missing_profile_repair_preserves_setup_recovery_and_request_routes(self):
        from datetime import timedelta
        from django.utils import timezone
        from social.models import AccountEmailProof
        from .email_verification import digest

        for purpose, route, field in [('signup', 'complete_signup', 'password1'),
                                      ('recovery', 'complete_recovery', 'new_password1')]:
            token = 'header-regression-' + purpose
            proof = AccountEmailProof.objects.create(email='owner@example.invalid', purpose=purpose,
                user=self.user if purpose == 'recovery' else None,
                token_digest=digest(token), expires_at=timezone.now()+timedelta(hours=1))
            self.user.profile.delete()
            page = self.client.get(reverse(route, args=[token]))
            self.assertContains(page, f'name="{field}"')
            self.user.refresh_from_db()
            self.assertFalse(self.user.profile.can_use_belong)
            self.assertFalse(self.user.profile.legacy_access)
            proof.refresh_from_db()
            self.assertIsNone(proof.used_at)
        for route in ['password_reset', 'account_email_requested']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        denied = self.client.post(reverse('activities:create'), HTTP_HX_REQUEST='true')
        self.assertEqual(denied['HX-Redirect'], reverse('verification_status'))
