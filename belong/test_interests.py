import importlib
import re
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from activities.models import Activity
from groups.models import Group
from social.models import Interest, InterestSuggestion


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InterestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('interests-user', email='interests@example.com', password='Testing-only-817!')
        self.user.profile.email_verified_at = timezone.now()
        self.user.profile.save()
        self.client.force_login(self.user)
        self.url = reverse('account_interests')

    def test_seed_is_complete_stable_and_idempotent_and_shared(self):
        migration = importlib.import_module('social.migrations.0008_seed_interests')
        self.assertEqual(Interest.objects.count(), 37)
        before = list(Interest.objects.values_list('slug', 'pk'))
        migration.seed_interests(apps, SimpleNamespace(connection=connection))
        self.assertEqual(before, list(Interest.objects.values_list('slug', 'pk')))
        for model in [Activity, Group, type(self.user.profile)]:
            self.assertIs(model._meta.get_field('interests').remote_field.model, Interest)
        self.assertNotEqual(Activity._meta.get_field('category').remote_field.model, Interest)

    def test_save_cross_section_edit_remove_and_empty(self):
        choices = list(Interest.objects.filter(slug__in=['walking-hiking', 'board-card-games', 'volunteering']))
        self.assertRedirects(self.client.post(self.url, {'interests': [i.pk for i in choices]}), reverse('account_settings'))
        for interest in choices:
            self.assertContains(self.client.get(reverse('account_settings')), escape(interest.name))
        page = self.client.get(self.url)
        self.assertContains(page, 'checked', count=3)
        self.client.post(self.url, {'interests': [choices[0].pk]})
        self.assertEqual(list(self.user.profile.interests.all()), [choices[0]])
        self.client.post(self.url, {})
        self.assertFalse(self.user.profile.interests.exists())

    def test_unknown_tags_and_over_limit_rejected_without_partial_writes(self):
        current = Interest.objects.first()
        self.user.profile.interests.add(current)
        for payload in [{'interests': ['999999']}, {'interests': ['arbitrary-tag']},
                        {'interests': list(Interest.objects.values_list('pk', flat=True)[:21])}]:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, {**payload, 'suggestion': 'Not saved'})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertEqual(list(self.user.profile.interests.all()), [current])
                self.assertFalse(InterestSuggestion.objects.exists())
        self.client.post(self.url, {'interests': list(Interest.objects.values_list('pk', flat=True)[:20])})
        self.assertEqual(self.user.profile.interests.count(), 20)

    def test_suggestions_are_private_separate_and_length_limited(self):
        count = Interest.objects.count()
        self.client.post(self.url, {'suggestion': '  Urban sketch walks  '})
        self.assertEqual(InterestSuggestion.objects.get(profile=self.user.profile).text, 'Urban sketch walks')
        self.assertEqual(Interest.objects.count(), count)
        self.assertFalse(self.user.profile.interests.exists())
        self.assertNotContains(self.client.get(reverse('account_settings')), 'Urban sketch walks')
        response = self.client.post(self.url, {'suggestion': 'a' * 301})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(InterestSuggestion.objects.count(), 1)

    def test_new_verified_signup_is_prompted_and_skip_ignores_unsaved_choices(self):
        self.client.logout()
        self.client.post(reverse('signup'), {'email': 'newinterests@example.com', 'display_name': 'New Person',
            'account_type': 'individual', 'password1': 'Testing-only-817!', 'password2': 'Testing-only-817!'})
        user = get_user_model().objects.get(email='newinterests@example.com')
        self.assertRedirects(self.client.get(self.url), reverse('verification_status'))
        token = re.search(r'/accounts/verify/([^/]+)/', mail.outbox[-1].body).group(1)
        self.assertRedirects(self.client.post(reverse('verify_email', args=[token])), self.url)
        self.assertContains(self.client.get(self.url), 'Skip for now')
        self.assertRedirects(self.client.post(self.url, {'action': 'skip', 'interests': [Interest.objects.first().pk], 'suggestion': 'Do not submit'}), reverse('activities:index'))
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.interests_prompt_pending)
        self.assertFalse(user.profile.interests.exists())
        self.assertFalse(InterestSuggestion.objects.exists())
        self.assertNotContains(self.client.get(self.url), 'Skip for now')

    def test_onboarding_save_zero_and_return_on_login_after_cross_browser_proof(self):
        profile = self.user.profile
        profile.interests_prompt_pending = True
        profile.save()
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('login'), {'username': self.user.email, 'password': 'Testing-only-817!'}), self.url)
        self.assertRedirects(self.client.post(self.url, {}), reverse('activities:index'))
        profile.refresh_from_db()
        self.assertFalse(profile.interests_prompt_pending)

    def test_existing_account_not_forced_to_onboard_and_editor_is_private(self):
        self.assertFalse(self.user.profile.interests_prompt_pending)
        self.assertNotContains(self.client.get(self.url), 'Skip for now')
        other = get_user_model().objects.create_user('other', email='other@example.com')
        interest = Interest.objects.first()
        other.profile.interests.add(interest)
        self.client.post(self.url, {'interests': []})
        self.assertTrue(other.profile.interests.filter(pk=interest.pk).exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
