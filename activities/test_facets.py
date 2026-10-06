from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from social.models import Friendship
from .forms import ActivityForm
from .models import Activity, ActivityResponse

NOW = datetime(2026, 10, 5, 2, tzinfo=dt_timezone.utc)


class FacetTests(TestCase):
    def setUp(self):
        self.host = get_user_model().objects.create_user(username='facet-host')
        self.viewer = get_user_model().objects.create_user(username='facet-viewer')
        Friendship.make_pair(self.host, self.viewer)
        self.client.force_login(self.viewer)

    def activity(self, title, **values):
        return Activity.objects.create(host=self.host, title=title, description='Shared activity', **values)

    def page(self, params=None):
        with patch('activities.discovery.timezone.now', return_value=NOW):
            return self.client.get(reverse('activities:index'), params or {})

    def ids(self, params):
        return {a.pk for a in self.page(params).context['activities']}

    def test_cost_tiers_are_numeric_disjoint_and_display_prose_is_not_parsed(self):
        cases = [(0, 'free'), ('0.50', '1_10'), (1, '1_10'), (10, '1_10'), ('10.01', '11_25'), (25, '11_25'), ('25.01', '26_50'), (50, '26_50'), ('50.01', '51_100'), (100, '51_100'), ('100.01', '100_plus')]
        expected = {}
        for amount, tier in cases:
            activity = self.activity(str(amount), cost_type='free' if amount == 0 else 'paid', cost_amount=Decimal(str(amount)), cost_display='Human-readable custom price')
            expected.setdefault(tier, set()).add(activity.pk)
        prose = self.activity('Price prose only', cost_type='paid', cost_display='$5')
        unknown = self.activity('Unknown price', cost_type='unknown', cost_display='Free-ish')
        for tier, ids in expected.items():
            self.assertEqual(self.ids({'cost': tier}), ids)
        self.assertEqual(self.ids({'cost': ['free', '1_10']}), expected['free'] | expected['1_10'])
        self.assertEqual(self.page().context['page_obj'].paginator.count, len(cases) + 2)

    def test_distance_buckets_or_online_hybrid_and_no_coordinates(self):
        points = [0, 1, 3, 5, 10, 25, 30]
        physical = [self.activity(str(d), location_type='in_person', location_gps=f'0,{d}') for d in points]
        online = self.activity('Online', location_type='online', location_gps='0,0')
        hybrid = self.activity('Hybrid', location_type='hybrid', location_gps='0,3')
        missing = self.activity('Missing coordinates', location_type='in_person')
        with patch('activities.discovery.distance_miles', side_effect=lambda origin, point: point[1]):
            for bucket, ids in [('under_1', {physical[0].pk}), ('1_3', {physical[1].pk}), ('3_5', {physical[2].pk, hybrid.pk}), ('5_10', {physical[3].pk}), ('10_25', {physical[4].pk}), ('25_plus', {physical[5].pk, physical[6].pk})]:
                self.assertEqual(self.ids({'where': bucket, 'lat': '0', 'lon': '0'}), ids)
            self.assertEqual(self.ids({'where': ['online', 'under_1'], 'lat': '0', 'lon': '0'}), {online.pk, hybrid.pk, physical[0].pk})
        denied = self.page({'where': ['online', 'under_1'], 'lat': 'nan', 'lon': '0'})
        self.assertEqual(denied.context['filter_params'].getlist('where'), ['online'])
        self.assertEqual({a.pk for a in denied.context['activities']}, {online.pk, hybrid.pk})
        self.assertContains(denied, 'Allow location access')
        self.assertNotIn(missing.pk, self.ids({'where': 'online'}))

    def test_when_options_local_calendar_now_and_open_ended(self):
        recent = self.activity('Recent start', starts_at=NOW-timedelta(hours=1))
        current = self.activity('Long active event', starts_at=NOW-timedelta(days=2), ends_at=NOW+timedelta(hours=1))
        ended = self.activity('Ended', starts_at=NOW-timedelta(hours=1), ends_at=NOW-timedelta(minutes=1))
        stale = self.activity('Old start', starts_at=NOW-timedelta(days=30))
        intent = self.activity('Now intent', freetext_when='Now')
        open_ended = self.activity('Open ended')
        tomorrow = self.activity('Tomorrow', starts_at=NOW+timedelta(hours=12))
        monday_edge = self.activity('Monday edge', starts_at=datetime(2026, 10, 5, 4, tzinfo=dt_timezone.utc))
        saturday = self.activity('Saturday', starts_at=datetime(2026, 10, 3, 16, tzinfo=dt_timezone.utc))
        self.assertEqual(self.ids({'when': 'now'}), {recent.pk, current.pk, intent.pk})
        self.assertEqual(self.ids({'when': 'today'}), {recent.pk, ended.pk})
        self.assertEqual(self.ids({'when': 'tomorrow'}), {tomorrow.pk, monday_edge.pk})
        self.assertEqual(self.ids({'when': 'week'}), {recent.pk, ended.pk})
        self.assertEqual(self.ids({'when': 'weekend'}), {saturday.pk, recent.pk, ended.pk})
        self.assertEqual(self.ids({'when': 'open'}), {intent.pk, open_ended.pk})
        self.assertEqual(self.ids({'when': ['now', 'tomorrow']}), {recent.pk, current.pk, intent.pk, tomorrow.pk, monday_edge.pk})

    def test_facets_combine_and_audience_is_exact_not_viewer_eligibility(self):
        friend = self.activity('Friend activity', audience='friends', cost_type='paid', cost_amount=5, location_type='hybrid', starts_at=NOW)
        public = self.activity('Public activity', audience='everyone', cost_type='free', location_type='online', starts_at=NOW)
        extended = self.activity('Extended activity', audience='extended_friends', cost_type='paid', cost_amount=100, starts_at=NOW)
        self.assertEqual(self.ids({'audience': 'friends'}), {friend.pk})
        self.assertEqual(self.ids({'audience': ['friends', 'everyone'], 'cost': ['free', '1_10'], 'where': 'online', 'when': 'today'}), {friend.pk, public.pk})
        self.assertEqual(self.ids({'cost': '1_10', 'audience': 'everyone'}), set())
        self.assertEqual(self.ids({'when': [], 'cost': [], 'where': [], 'audience': []}), {friend.pk, public.pk, extended.pk})

    def test_repeated_facets_survive_pagination_and_plain_response_redirect(self):
        for n in range(15):
            self.activity(f'Match {n}', cost_type='paid', cost_amount=5, starts_at=NOW)
        params = {'q': 'Match', 'when': ['today', 'tomorrow'], 'cost': ['free', '1_10'], 'hidden': 'include'}
        page = self.page(params)
        query = page.context['pagination_query']
        self.assertEqual(parse_qs(query), params | {'q': ['Match'], 'hidden': ['include']})
        self.assertEqual(len(self.page({**params, 'page': 2}).context['activities']), 3)
        activity = page.context['activities'][0]
        destination = '/?' + query
        response = self.client.post(reverse('activities:respond', args=[activity.pk]), {'status': 'interested', 'variant': 'card', 'next': destination})
        self.assertEqual(response.headers['Location'], destination)
        self.assertTrue(ActivityResponse.objects.filter(user=self.viewer, activity=activity).exists())

    def test_forms_validate_numeric_cost_and_display_exact_cost(self):
        values = {'title': 'Cost example', 'description': 'Try together', 'audience': 'everyone', 'location_type': 'online', 'cost_type': 'paid', 'cost_amount': '5.25'}
        for overrides, field in [({'cost_amount': '-1'}, 'cost_amount'), ({'cost_type': 'free'}, 'cost_amount'), ({'cost_type': 'unknown'}, 'cost_type'), ({'cost_amount': '0'}, 'cost_type')]:
            form = ActivityForm(values | overrides)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        form = ActivityForm(values)
        self.assertTrue(form.is_valid(), form.errors)
        activity = form.save(commit=False)
        activity.host = self.host
        activity.save()
        self.assertContains(self.page(), '$5.25')
        self.assertContains(self.client.get(reverse('activities:detail', args=[activity.pk])), '$5.25')
