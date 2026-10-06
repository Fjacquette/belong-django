from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .card_style import response_accent
from .forms import ActivityForm
from .models import Activity


def contrast_with_white(color):
    values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 1.05 / (sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722))) + 0.05)


class CardFitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = get_user_model().objects.create_user(username='fit-host')
        cls.activity = Activity.objects.create(host=cls.host, title='Paddling together',
                                             freetext_when='Saturday morning', location_name='River park',
                                             color_primary='#06796b')

    def setUp(self):
        self.client.force_login(self.host)

    def form(self, **overrides):
        return ActivityForm(data={'title': 'Walk together', 'description': 'A short walk',
                                  'location_type': 'in_person', 'audience': 'everyone',
                                  'cost_type': 'free', **overrides}, user=self.host)

    def test_form_limits_apply_to_creation_and_instance_edits_without_storage_changes(self):
        self.assertEqual(Activity._meta.get_field('title').max_length, 160)
        self.assertEqual(Activity._meta.get_field('location_name').max_length, 200)
        for field, limit in [('title', 48), ('location_name', 40)]:
            for char in ['W', 'i']:
                with self.subTest(field=field, char=char):
                    self.assertTrue(self.form(**{field: char * limit}).is_valid())
                    invalid = self.form(**{field: char * (limit+1)})
                    self.assertFalse(invalid.is_valid())
                    self.assertIn(field, invalid.errors)
                    edited = ActivityForm(invalid.data, instance=self.activity, user=self.host)
                    self.assertFalse(edited.is_valid())
                    self.assertIn(field, edited.errors)

    def test_creation_exposes_limits_counters_guidance_and_keeps_overlimit_input(self):
        response = self.client.get(reverse('activities:create'))
        self.assertContains(response, 'maxlength="48"')
        self.assertContains(response, 'maxlength="40"')
        self.assertContains(response, 'data-counter-for="id_title"')
        self.assertContains(response, 'data-counter-for="id_location_name"')
        self.assertContains(response, 'id_title_helptext id_title_counter')
        self.assertContains(response, 'Put the full address and directions below.')
        count = Activity.objects.count()
        invalid = self.client.post(reverse('activities:create'), self.form(title='W'*49).data)
        self.assertContains(invalid, '49 / 48')
        self.assertEqual(Activity.objects.count(), count)

    def test_structured_logistics_menu_position_and_card_response_variant(self):
        response = self.client.get(reverse('activities:index'))
        html = response.content.decode()
        first = html.split('activity-card__band-1', 1)[1].split('activity-card__band-2', 1)[0]
        second = html.split('activity-card__band-2', 1)[1].split('activity-card__band-3', 1)[0]
        self.assertIn('card-context-menu__trigger', first)
        self.assertNotIn('ui-menu-trigger', first)
        self.assertNotIn('card-context-menu', second)
        self.assertIn('activity-card__when', first)
        self.assertIn('activity-card__where', first)
        self.assertIn('title="Saturday morning"', first)
        self.assertIn('title="River park"', first)
        self.assertContains(response, 'ui-response--card')
        detail = self.client.get(reverse('activities:detail', args=[self.activity.pk]))
        self.assertNotContains(detail, 'ui-response--card')

    def test_palette_accents_are_readable_and_preserve_usable_colors(self):
        for color in ['#06796b', '#B81C57', '#143CA6', '#FFFFFF', '#00FF00', '#FFFF00', '#ffcccc', '#000000']:
            with self.subTest(color=color):
                accent = response_accent(color)
                self.assertGreaterEqual(contrast_with_white(accent), 4.5)
                if contrast_with_white(color) >= 4.5:
                    self.assertEqual(accent, color.lower())
        self.assertEqual(response_accent('invalid'), '#333333')

    def test_card_fragment_retains_structured_fit_and_palette_after_response(self):
        response = self.client.post(reverse('activities:respond', args=[self.activity.pk]),
                                    {'status': 'interested', 'variant': 'card', 'next': '/?cost=free'},
                                    HTTP_HX_REQUEST='true')
        self.assertContains(response, 'activity-card__when')
        self.assertContains(response, 'card-context-menu__trigger')
        self.assertContains(response, '--card-accent: #06796b;')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, 'ui-response--card')
