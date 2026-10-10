from django.test import TestCase
from django.urls import reverse

from belong.test_helpers import create_legacy_user
from .models import Activity, HiddenActivity


class ProductionDiscoverModeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_legacy_user(username='discover-modes')
        for number in range(52):
            Activity.objects.create(host=cls.user, title=f'Test walk {number}', description='A free walk')

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('activities:index')

    def test_result_batch_is_distinct_from_visible_card_set(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['activities']), 48)
        self.assertEqual(response.context['page_obj'].paginator.count, 52)
        self.assertContains(response, 'data-paged-controls')
        self.assertContains(response, 'data-total="52"')
        self.assertContains(response, 'data-batch-start="1"')
        self.assertContains(response, 'data-stack-root')
        self.assertContains(response, 'js/card-view.js')
        self.assertNotContains(response, 'js/discovery-prototype.js')

        later = self.client.get(self.url, {'page': '2'})
        self.assertEqual(len(later.context['activities']), 4)
        self.assertContains(later, 'data-batch-start="49"')
        self.assertContains(later, 'data-total="52"')
        self.assertEqual(response.context['page_obj'].paginator.num_pages, 2)

    def test_all_discover_filters_still_apply_before_batching(self):
        hidden = Activity.objects.filter(title='Test walk 0').get()
        HiddenActivity.objects.create(user=self.user, activity=hidden)
        response = self.client.get(self.url, {'q': 'Test walk'})
        self.assertEqual(response.context['page_obj'].paginator.count, 51)
        self.assertNotContains(response, 'Test walk 0</a>')
        only_hidden = self.client.get(self.url, {'hidden': 'only'})
        self.assertEqual(only_hidden.context['page_obj'].paginator.count, 1)

    def test_production_controls_are_separate_from_card_markup(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="card-view" value="paged"')
        self.assertContains(response, 'name="card-view" value="stacked"')
        self.assertContains(response, 'name="card-view" value="all"')
        self.assertContains(response, 'name="card-density" value="regular"')
        self.assertContains(response, 'name="card-density" value="tight"')
        self.assertNotContains(response, 'data-prototype-expose')
        self.assertTemplateUsed(response, 'activities/_card.html')

    def test_three_filtered_batches_cover_every_matching_activity_once(self):
        for number in range(53):
            Activity.objects.create(host=self.user, title=f'Test walk extra {number}', description='A free walk')
        expected = list(Activity.objects.filter(host=self.user).order_by('-starts_at', '-created_at').values_list('pk', flat=True))
        found = []
        for page in range(1, 4):
            response = self.client.get(self.url, {'q': 'Test walk', 'page': page, 'hidden': 'include'})
            found.extend(activity.pk for activity in response.context['activities'])
            self.assertEqual(response.context['page_obj'].paginator.count, 105)
            if page < 3:
                self.assertContains(response, f'page={page + 1}')
                self.assertContains(response, 'q=Test+walk')
                self.assertContains(response, 'hidden=include')
        self.assertEqual(found, expected)
        self.assertEqual(len(set(found)), 105)
