from belong.test_helpers import create_legacy_user
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Activity, ActivityCategory, ActivityResponse, HiddenActivity, HiddenOrganizer


class CardContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.viewer = create_legacy_user(username='context-viewer')
        cls.host = create_legacy_user(username='context-host')
        cls.other = create_legacy_user(username='context-other')
        cls.category = ActivityCategory.objects.create(name='Walks', slug='walks')
        defaults = dict(title='A walk', host=cls.host, category=cls.category,
                        starts_at=datetime(2026, 10, 6, 14, tzinfo=timezone.utc),
                        location_type='in_person', location_name='River park', cost_type='free')
        cls.first = Activity.objects.create(**defaults)
        cls.same = Activity.objects.create(**{**defaults, 'host': cls.other, 'starts_at': datetime(2026, 10, 6, 18, tzinfo=timezone.utc)})
        cls.different = Activity.objects.create(**{**defaults, 'starts_at': datetime(2026, 10, 7, 14, tzinfo=timezone.utc), 'location_name': 'Hill park', 'category': None})
        cls.private = Activity.objects.create(**{**defaults, 'host': cls.other, 'audience': 'friends'})

    def setUp(self):
        self.client.force_login(self.viewer)

    def ids(self, params=None):
        return {a.pk for a in self.client.get(reverse('activities:index'), params or {}).context['activities']}

    def test_context_filters_match_visible_organizer_local_day_place_category(self):
        for params, expected in [
            ({'organizer': self.host.pk}, {self.first.pk, self.different.pk}),
            ({'context_time': self.first.pk}, {self.first.pk, self.same.pk}),
            ({'context_place': self.first.pk}, {self.first.pk, self.same.pk}),
            ({'category': self.category.slug}, {self.first.pk, self.same.pk}),
            ({'context_time': self.first.pk, 'context_place': self.different.pk}, set()),
        ]:
            with self.subTest(params=params):
                self.assertEqual(self.ids(params), expected)

    def test_menu_links_keep_repeated_filters_search_and_drop_page(self):
        params = {'q': 'walk', 'cost': ['free', '1_10'], 'audience': ['everyone'], 'page': '2'}
        response = self.client.get(reverse('activities:index'), params)
        activity = next(a for a in response.context['activities'] if a.pk == self.first.pk)
        self.assertEqual(len(activity.context_actions), 4)
        for action in activity.context_actions:
            query = parse_qs(urlsplit(action['url']).query)
            self.assertEqual(urlsplit(action['url']).path, reverse('activities:index'))
            self.assertEqual(query['cost'], ['free', '1_10'])
            self.assertEqual(query['q'], ['walk'])
            self.assertNotIn('page', query)
        active = self.client.get(reverse('activities:index'), {**params, 'organizer': self.host.pk}).context['active_context']
        query = parse_qs(urlsplit(active[0]['clear_url']).query)
        self.assertNotIn('organizer', query)
        self.assertEqual(query['cost'], ['free', '1_10'])

    def test_context_survives_toolbar_pagination_and_htmx_response(self):
        destination = f'/?organizer={self.host.pk}&context_time={self.first.pk}&context_place={self.first.pk}&category=walks&cost=free&q=walk'
        page = self.client.get(destination)
        for key in ['organizer', 'context_time', 'context_place']:
            self.assertContains(page, f'name="{key}"')
            self.assertIn(key+'=', page.context['pagination_query'])
        response = self.client.post(reverse('activities:respond', args=[self.first.pk]),
                                    {'status': 'interested', 'variant': 'card', 'next': destination}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'More from this organizer')
        self.assertContains(response, 'context_time=')
        self.assertContains(response, 'cost=free')
        self.assertContains(response, f'data-share-url="{reverse("activities:detail", args=[self.first.pk])}" hidden')
        plain = self.client.post(reverse('activities:respond', args=[self.first.pk]),
                                 {'status': 'interested', 'variant': 'card', 'next': destination})
        self.assertRedirects(plain, destination)

    def test_share_uses_details_url_and_escaped_activity_title(self):
        self.first.title = 'A walk "together" <outside>'
        self.first.save()
        response = self.client.get('/', {'q': 'walk', 'cost': ['free', '1_10'], 'page': '2'})
        url = reverse('activities:detail', args=[self.first.pk])
        self.assertContains(response, f'data-share-title="{escape(self.first.title)}" data-share-url="{url}" hidden')
        self.assertContains(response, 'data-share-feedback role="status"')
        self.assertContains(response, 'aria-label="Activity link"')
        self.assertContains(response, 'More from this organizer')
        self.assertContains(response, 'Hide this activity')
        self.assertContains(response, "Hide this organizer's activities")

    def test_share_does_not_disclose_an_invisible_activity(self):
        response = self.client.get('/')
        url = reverse('activities:detail', args=[self.private.pk])
        self.assertNotContains(response, f'data-share-url="{url}"')
        fragment = self.client.post(reverse('activities:respond', args=[self.private.pk]),
                                    {'status': 'interested', 'variant': 'card'}, HTTP_HX_REQUEST='true')
        self.assertEqual(fragment.status_code, 404)
        self.assertNotContains(fragment, 'data-share-activity', status_code=404)

    def test_organizer_hiding_is_private_idempotent_reversible_and_preserves_responses(self):
        ActivityResponse.objects.create(user=self.viewer, activity=self.first, status='interested')
        url = reverse('activities:hide_organizer', args=[self.first.pk])
        destination = '/?q=walk&cost=free&audience=everyone'
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {'next': destination}), destination)
        self.assertEqual(HiddenOrganizer.objects.filter(user=self.viewer).count(), 1)
        self.assertEqual(self.ids(), {self.same.pk})
        self.assertEqual(self.ids({'hidden': 'only'}), {self.first.pk, self.different.pk})
        self.assertEqual(self.ids({'hidden': 'include'}), {self.first.pk, self.same.pk, self.different.pk})
        self.client.force_login(self.other)
        self.assertIn(self.first.pk, self.ids())
        self.client.force_login(self.viewer)
        recovery = self.client.get('/?hidden=include')
        self.assertContains(recovery, "Unhide this organizer's activities")
        self.client.post(url, {'hidden': '0', 'next': '/?hidden=include'})
        self.assertIn(self.first.pk, self.ids())
        self.assertTrue(ActivityResponse.objects.filter(user=self.viewer, activity=self.first, status='interested').exists())

    def test_hidden_recovery_includes_either_preference_and_retains_activity_hiding(self):
        HiddenActivity.objects.create(user=self.viewer, activity=self.first)
        HiddenOrganizer.objects.create(user=self.viewer, organizer=self.other)
        self.assertEqual(self.ids({'hidden': 'only'}), {self.first.pk, self.same.pk})
        self.client.post(reverse('activities:hide_organizer', args=[self.same.pk]), {'hidden': '0'})
        self.assertEqual(self.ids({'hidden': 'only'}), {self.first.pk})

    def test_private_invalid_context_and_suppression_cannot_bypass_visibility(self):
        for key in ['context_time', 'context_place']:
            self.assertEqual(self.ids({key: self.private.pk}), self.ids())
            self.assertEqual(self.ids({key: 'invalid'}), self.ids())
        url = reverse('activities:hide_organizer', args=[self.private.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(HiddenOrganizer.objects.exists())
        safe = reverse('activities:hide_organizer', args=[self.first.pk])
        self.assertRedirects(self.client.post(safe, {'next': 'https://evil.example/'}), reverse('activities:index'))

    def test_freetext_time_and_online_place_and_unknown_context(self):
        now = Activity.objects.create(host=self.host, title='Online now', freetext_when='Now', location_type='online')
        hybrid = Activity.objects.create(host=self.host, title='Hybrid now', freetext_when='Now', location_type='hybrid')
        unknown = Activity.objects.create(host=self.host, title='Unresolved')
        self.assertEqual(self.ids({'context_time': now.pk}), {now.pk, hybrid.pk})
        self.assertEqual(self.ids({'context_place': now.pk}), {now.pk, hybrid.pk})
        response = self.client.get('/')
        card = next(a for a in response.context['activities'] if a.pk == unknown.pk)
        self.assertEqual([action['label'] for action in card.context_actions], ['More from this organizer'])

    def test_context_day_respects_local_midnight_and_excludes_adjacent_day(self):
        same_day = Activity.objects.create(host=self.host, title='Late walk',
                                          starts_at=datetime(2026, 10, 7, 3, tzinfo=timezone.utc))
        previous_day = Activity.objects.create(host=self.host, title='Earlier walk',
                                              starts_at=datetime(2026, 10, 6, 3, tzinfo=timezone.utc))
        results = self.ids({'context_time': self.first.pk})
        self.assertIn(same_day.pk, results)
        self.assertNotIn(previous_day.pk, results)

    def test_suppression_includes_future_activities_and_requires_csrf(self):
        from django.test import Client
        url = reverse('activities:hide_organizer', args=[self.first.pk])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.viewer)
        self.assertEqual(protected.post(url).status_code, 403)
        self.assertFalse(HiddenOrganizer.objects.exists())
        self.client.post(url)
        future = Activity.objects.create(host=self.host, title='Newly created')
        self.assertNotIn(future.pk, self.ids())
        self.assertIn(future.pk, self.ids({'hidden': 'include'}))
