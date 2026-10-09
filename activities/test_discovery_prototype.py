from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from belong.test_helpers import create_legacy_user
from .models import Activity, ActivityResponse, ActivityVisibility, HiddenActivity


class DiscoveryPrototypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_legacy_user(username='prototype-reviewer')
        for i in range(55):
            Activity.objects.create(host=cls.user, title=f'Walk {i}', description='A free walk')

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('activities:index')

    @override_settings(ENVIRONMENT='production', DEBUG=True)
    def test_production_does_not_expose_experiment_even_with_debug(self):
        self.assertEqual(self.client.get(self.url, {'prototype': 'stack'}).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    @override_settings(ENVIRONMENT='test')
    def test_default_discover_keeps_twelve_card_pagination_and_existing_assets(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'js/discovery-prototype.js')
        self.assertNotContains(response, 'data-prototype-controls')
        self.assertContains(response, 'js/card-view.js')
        self.assertEqual(len(response.context['activities']), 12)
        self.assertContains(response, 'Page 1 of 5')
        self.assertEqual(len(self.client.get(self.url, {'page': '2'}).context['activities']), 12)

    @override_settings(ENVIRONMENT='dev')
    def test_prototype_uses_full_filtered_authorized_collection_without_pagination(self):
        other = create_legacy_user(username='other-host')
        Activity.objects.create(host=other, title='Walk private', audience=ActivityVisibility.CUSTOM)
        Activity.objects.create(host=self.user, title='Cycling')
        hidden = Activity.objects.filter(title='Walk 1').get()
        HiddenActivity.objects.create(user=self.user, activity=hidden)
        response = self.client.get(self.url, {'q': 'Walk', 'page': '2', 'prototype': 'stack'})
        self.assertEqual(len(response.context['activities']), 54)
        expected = list(Activity.objects.filter(host=self.user, title__icontains='Walk').exclude(pk=hidden.pk).order_by('-starts_at', '-created_at').values_list('pk', flat=True))
        self.assertEqual([a.pk for a in response.context['activities']], expected)
        self.assertIsNone(response.context['page_obj'])
        self.assertNotContains(response, 'Page 2 of')
        self.assertNotContains(response, 'page=3')
        self.assertNotContains(response, 'Walk private')
        self.assertContains(response, 'name="prototype" value="stack"')
        self.assertTemplateUsed(response, 'activities/_card.html')
        self.assertContains(response, 'data-prototype-scroll')
        self.assertContains(response, 'js/discovery-prototype.js')
        self.assertNotContains(response, 'js/card-view.js')
        self.assertFalse(ActivityResponse.objects.exists())

    @override_settings(ENVIRONMENT='test')
    def test_safe_experiment_limit_is_explicit_and_does_not_change_normal_page_size(self):
        with patch('activities.views.PROTOTYPE_LIMIT', 20):
            response = self.client.get(self.url, {'prototype': 'stack'})
        self.assertEqual(len(response.context['activities']), 20)
        self.assertTrue(response.context['prototype_limit_reached'])
        self.assertEqual(Activity.objects.count(), 55)

    @override_settings(ENVIRONMENT='test')
    def test_no_matches_has_only_unsaved_inert_template_source_for_client_demos(self):
        response = self.client.get(self.url, {'prototype': 'stack', 'q': 'nonexistent'})
        self.assertEqual(response.context['activities'], [])
        self.assertContains(response, '<template data-prototype-demo-template>')
        self.assertTrue(response.context['prototype_demo']._state.adding)
        self.assertEqual(Activity.objects.count(), 55)
        self.assertFalse(ActivityResponse.objects.exists())
