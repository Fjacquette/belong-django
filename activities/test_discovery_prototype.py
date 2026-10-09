from django.test import TestCase, override_settings
from django.urls import reverse
from belong.test_helpers import create_legacy_user
from .models import Activity, ActivityResponse


class DiscoveryPrototypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_legacy_user(username='prototype-reviewer')
        for i in range(15):
            Activity.objects.create(host=cls.user, title=f'Walk {i}', description='A free walk')

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('activities:index')

    @override_settings(ENVIRONMENT='production', DEBUG=True)
    def test_production_does_not_expose_experiment_even_with_debug(self):
        self.assertEqual(self.client.get(self.url, {'prototype': 'stack'}).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    @override_settings(ENVIRONMENT='test')
    def test_default_discover_has_no_prototype_assets_or_controls(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'js/discovery-prototype.js')
        self.assertNotContains(response, 'Layout prototype')
        self.assertContains(response, 'js/card-view.js')

    @override_settings(ENVIRONMENT='dev')
    def test_opt_in_reuses_filtered_order_pagination_and_cards_without_writes(self):
        params = {'q': 'Walk', 'page': '2'}
        ordinary = self.client.get(self.url, params)
        prototype = self.client.get(self.url, {**params, 'prototype': 'stack'})
        self.assertEqual([a.pk for a in ordinary.context['activities']],
                         [a.pk for a in prototype.context['activities']])
        experimental_filters = prototype.context['filter_params'].copy()
        experimental_filters.pop('prototype')
        self.assertEqual(ordinary.context['filter_params'], experimental_filters)
        self.assertContains(prototype, 'name="prototype" value="stack"')
        self.assertIn('prototype=stack', prototype.context['pagination_query'])
        self.assertTemplateUsed(prototype, 'activities/_card.html')
        self.assertContains(prototype, 'js/discovery-prototype.js')
        self.assertNotContains(prototype, 'js/card-view.js')
        self.assertEqual(Activity.objects.count(), 15)
        self.assertFalse(ActivityResponse.objects.exists())
