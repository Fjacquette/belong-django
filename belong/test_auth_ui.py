from django.contrib.auth import get_user_model
from django.test import TestCase
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
        self.assertContains(response, "Please enter a correct username and password")
        self.assertContains(response, f'name="next" value="{destination}"')
        get_user_model().objects.create_user(username="auth-review", password="test-only-password-13")
        response = self.client.post(reverse("login"), {"username": "auth-review", "password": "test-only-password-13", "next": destination})
        self.assertRedirects(response, destination)

    def test_signup_validation_remains_visible_without_creating_an_account(self):
        response = self.client.post(reverse("signup"), {"username": "new-reviewer", "password1": "short", "password2": "different"})
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertFalse(get_user_model().objects.filter(username="new-reviewer").exists())

    def test_authenticated_product_navigation_is_retained(self):
        user = get_user_model().objects.create_user(username="navigation-review")
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
        data = {'username': 'ordinary-signup', 'password1': 'Testing-normal-817!', 'password2': 'Testing-normal-817!'}
        self.assertContains(self.client.post(reverse('signup'), data), 'This field is required')
        self.assertFalse(get_user_model().objects.filter(username='ordinary-signup').exists())
        data['email'] = 'New.Person@EXAMPLE.com'
        self.assertRedirects(self.client.post(reverse('signup'), data), reverse('activities:index'))
        self.assertEqual(get_user_model().objects.get(username='ordinary-signup').email, 'new.person@example.com')

    def test_normal_signup_rejects_email_already_claimed_case_insensitively(self):
        get_user_model().objects.create_user('existing-email', email='Existing@Example.com')
        response = self.client.post(reverse('signup'), {'username': 'duplicate-email', 'email': 'existing@example.COM',
                                    'password1': 'Testing-normal-817!', 'password2': 'Testing-normal-817!'})
        self.assertContains(response, 'Sign in instead')
        self.assertFalse(get_user_model().objects.filter(username='duplicate-email').exists())
