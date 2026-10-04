from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from social.models import Friendship, UserProfile
from .forms import ActivityForm
from .models import Activity, ActivityCategory, ActivityResponse, HiddenActivity

NOW = datetime(2026, 10, 5, 2, tzinfo=dt_timezone.utc)  # October 4 in Eastern time.


class DiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = get_user_model().objects.create_user(username='discovery-host')
        cls.viewer = get_user_model().objects.create_user(username='discovery-viewer')
        cls.other = get_user_model().objects.create_user(username='discovery-other')
        cls.category = ActivityCategory.objects.create(name='Outdoors', slug='outdoors')
        defaults = dict(host=cls.host, description='Do something together', starts_at=NOW-timedelta(hours=1),
                        location_type='hybrid', location_gps='40.0,-75.0', cost_type='free', category=cls.category)
        cls.near = Activity.objects.create(title='Nearby today', **defaults)
        cls.paid = Activity.objects.create(title='Paid in person', **{**defaults, 'cost_type': 'paid', 'location_type': 'in_person'})
        cls.far = Activity.objects.create(title='Far today', **{**defaults, 'location_gps': '35,-80'})
        cls.open = Activity.objects.create(title='Open-ended online', **{**defaults, 'starts_at': None, 'location_type': 'online'})
        cls.unknown = Activity.objects.create(title='Unknown cost', cost_display='Free-ish?', **{**defaults, 'cost_type': 'unknown'})
        cls.tomorrow = Activity.objects.create(title='Tomorrow', **{**defaults, 'starts_at': NOW+timedelta(hours=12), 'location_gps': ''})

    def setUp(self):
        self.client.force_login(self.viewer)

    def discover(self, params=None):
        with patch('activities.discovery.timezone.now', return_value=NOW):
            return self.client.get(reverse('activities:index'), params or {})

    def ids(self, params):
        return {a.pk for a in self.discover(params).context['activities']}

    def test_today_uses_local_date_and_excludes_dateless(self):
        self.assertEqual(self.ids({'today': '1'}), {a.pk for a in [self.near, self.paid, self.far, self.unknown]})
        self.assertEqual(self.ids({'timing': 'dateless'}), {self.open.pk})
        self.assertEqual(self.ids({'timing': 'upcoming'}), {self.tomorrow.pk})

    def test_individual_and_cumulative_filters(self):
        self.assertEqual(self.ids({'online': '1'}), {a.pk for a in [self.near, self.far, self.open, self.unknown, self.tomorrow]})
        self.assertEqual(self.ids({'free': '1'}), {a.pk for a in [self.near, self.far, self.open, self.tomorrow]})
        location = {'nearby': '1', 'lat': '40', 'lon': '-75'}
        self.assertEqual(self.ids(location), {a.pk for a in [self.near, self.paid, self.open, self.unknown]})
        self.assertEqual(self.ids({**location, 'today': '1', 'online': '1', 'free': '1'}), {self.near.pk})
        self.assertEqual(self.ids({'location': 'in_person', 'cost': 'paid', 'category': 'outdoors'}), {self.paid.pk})
        self.assertEqual(self.ids({'cost': 'unknown'}), {self.unknown.pk})

    def test_nearby_radius_and_invalid_coordinates(self):
        from .discovery import coordinates, distance_miles
        self.assertLess(distance_miles((40,-75), (40.1,-75)), 25)
        self.assertGreater(distance_miles((40,-75), (40.5,-75)), 25)
        for value in ['nan,0', '91,0', '0,181', 'text', '0,0,0', 'inf,0']:
            self.assertIsNone(coordinates(value))
        self.near.location_gps = 'not coordinates'
        self.near.save()
        self.assertNotIn(self.near.pk, self.ids({'nearby': '1', 'lat': '40', 'lon': '-75'}))
        for location in [{}, {'lat': 'NaN', 'lon': '0'}, {'lat': '100', 'lon': '0'}]:
            response = self.discover({'nearby': '1', **location})
            self.assertContains(response, 'Nearby is off')
            self.assertFalse(next(f for f in response.context['quick_filters'] if f['name']=='nearby')['active'])

    def test_hide_unhide_are_private_and_preserve_participation(self):
        participation = ActivityResponse.objects.create(user=self.viewer, activity=self.near, status='question', note='Keep my question')
        url = reverse('activities:hide', args=[self.near.pk])
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {'hidden': '1'}), reverse('activities:index'))
        self.assertEqual(HiddenActivity.objects.count(), 1)
        self.assertNotIn(self.near.pk, self.ids({}))
        self.assertIn(self.near.pk, self.ids({'hidden': 'include'}))
        self.assertEqual(self.ids({'hidden': 'only'}), {self.near.pk})
        self.client.force_login(self.other)
        self.assertIn(self.near.pk, self.ids({}))
        HiddenActivity.objects.create(user=self.other, activity=self.near)
        self.client.force_login(self.viewer)
        response = self.client.post(url, {'hidden': '0'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.headers['HX-Refresh'], 'true')
        self.assertIn(self.near.pk, self.ids({}))
        self.assertTrue(HiddenActivity.objects.filter(user=self.other, activity=self.near).exists())
        participation.refresh_from_db()
        self.assertEqual((participation.status, participation.note), ('question','Keep my question'))

    def test_hide_respects_visibility_method_csrf_and_safe_redirect(self):
        self.near.audience = 'friends'
        self.near.save()
        url = reverse('activities:hide', args=[self.near.pk])
        self.assertEqual(self.client.post(url, {'hidden':'1'}).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(HiddenActivity.objects.exists())
        self.near.audience = 'everyone'
        self.near.save()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.viewer)
        self.assertEqual(client.post(url, {'hidden':'1'}).status_code, 403)
        self.assertRedirects(self.client.post(url, {'next':'https://example.com/'}), reverse('activities:index'))
        self.client.logout()
        self.assertEqual(self.client.post(url, {'hidden':'1'}).status_code, 302)

    def test_pagination_preserves_all_discovery_state(self):
        for n in range(15):
            Activity.objects.create(host=self.host, title=f'Match {n}', description='Match', category=self.category,
                                    starts_at=NOW, location_gps='40,-75', location_type='online', cost_type='free')
        params = {'q':'Match','category':'outdoors','today':'1','nearby':'1','lat':'40','lon':'-75','online':'1','free':'1','hidden':'include'}
        response = self.discover(params)
        self.assertTrue(response.context['page_obj'].has_next())
        from urllib.parse import parse_qs
        self.assertEqual(parse_qs(response.context['pagination_query']), {k:[v] for k,v in params.items()})
        self.assertContains(response, 'page=2')
        page2 = self.discover({**params,'page':'2'})
        self.assertEqual(len(page2.context['activities']), 3)

    def test_card_tooltips_details_private_buttons_and_floating_create(self):
        self.near.title = 'Long activity title ' * 8
        self.near.summary = 'Full summary ' * 20
        self.near.description = 'Full description ' * 80
        self.near.organizer_name = 'A long organizer name'
        self.near.save()
        response = self.discover({'q':'Long activity'})
        self.assertContains(response, f'title="{self.near.title}"')
        self.assertContains(response, f'title="{self.near.description}"')
        self.assertContains(response, f'title="{self.near.organizer_name}"')
        self.assertContains(response, 'Full details and all response choices')
        self.assertContains(response, '>Details</a>')
        self.assertContains(response, '>Hide</button>')
        self.assertContains(response, 'aria-label="Create activity"')
        self.assertNotContains(response, 'href="/discover/categories/"')

    def test_creator_vocabulary_and_toggle_to_clear(self):
        form = ActivityForm({'title':'Vote on dinner','description':'Choose together','audience':'everyone','location_type':'tbd',
                             'cost_type':'unknown','available_responses':['vote','more','question']})
        self.assertTrue(form.is_valid(), form.errors)
        activity = form.save(commit=False)
        activity.host = self.host
        activity.save()
        url = reverse('activities:respond', args=[activity.pk])
        response = self.client.post(url, {'variant':'card','status':'vote'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'Vote on details')
        self.assertContains(response, 'Tell me more')
        self.assertNotContains(response, 'name="status" value="interested"')
        self.assertContains(response, 'value="vote" aria-pressed="true"')
        response = self.client.post(url, {'variant':'card','status':'vote'}, HTTP_HX_REQUEST='true')
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer,activity=activity).exists())
        self.assertNotContains(response, 'aria-pressed="true"')
        detail = self.client.get(reverse('activities:detail',args=[activity.pk]))
        self.assertContains(detail, 'I have a question')
        self.assertEqual(self.client.post(url, {'status':'committed'}).status_code,200)
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer,activity=activity).exists())

    def test_presence_is_auth_activity_with_documented_states(self):
        for user, age, state in [(self.host,2,'Active'),(self.other,15,'Idle')]:
            Friendship.make_pair(self.viewer,user)
            UserProfile.objects.filter(user=user).update(last_active_at=NOW-timedelta(minutes=age))
        offline = get_user_model().objects.create_user(username='offline-friend')
        Friendship.make_pair(self.viewer,offline)
        self.assertIsNone(offline.profile.last_active_at)
        response = self.discover()
        states = {f['user'].username:f['presence'] for f in response.context['friends']}
        self.assertEqual(states, {self.host.username:'Active', self.other.username:'Idle', offline.username:'Offline'})
        self.assertContains(response,'Authenticated activity within 5 minutes')
        self.assertEqual(UserProfile.objects.get(user=self.viewer).last_active_at, NOW)
        self.client.logout()
        with patch('social.middleware.timezone.now',return_value=NOW+timedelta(hours=1)):
            self.client.get(reverse('login'))
        self.assertEqual(UserProfile.objects.get(user=self.viewer).last_active_at,NOW)
