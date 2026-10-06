from belong.test_helpers import create_legacy_user
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .card_style import header_gradient, response_accent
from .forms import ActivityForm
from .models import Activity


def contrast_with_white(color):
    values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 1.05 / (sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722))) + 0.05)


class CardFitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user(username='fit-host')
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
        self.assertNotIn('activity-card__when', first)
        self.assertNotIn('activity-card__where', first)
        self.assertNotIn('<strong>', second)
        self.assertIn('activity-card__when', second)
        self.assertIn('activity-card__where', second)
        self.assertIn('data-full-text="Saturday morning"', second)
        self.assertIn('data-full-text="River park"', second)
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

    def test_header_gradient_is_subtle_darkens_right_and_stays_accessible_throughout(self):
        for primary, secondary in [('#00ffff', '#ffffff'), ('#843A96', '#5C2969'),
                                   ('#ffffff', '#000000'), ('invalid', '#FFFF00')]:
            left, right = header_gradient(primary, secondary)
            a = [int(left[i:i+2], 16) for i in (1, 3, 5)]
            b = [int(right[i:i+2], 16) for i in (1, 3, 5)]
            self.assertTrue(all(y <= x for x, y in zip(a, b)))
            for step in range(11):
                color = '#' + ''.join(f'{round(x + (y-x)*step/10):02x}' for x, y in zip(a, b))
                self.assertGreaterEqual(contrast_with_white(color), 4.5)

    def test_title_preserves_author_casing_and_metadata_order(self):
        self.activity.title = 'D&D and OW2 Together'
        self.activity.save()
        response = self.client.get(reverse('activities:index'))
        self.assertContains(response, 'D&amp;D and OW2 Together')
        html = response.content.decode().split('activity-card__metadata', 1)[1]
        self.assertLess(html.index('Organized by'), html.index('activity-card__when'))
        self.assertLess(html.index('activity-card__where'), html.index('Everyone'))

    def test_card_full_text_uses_explicit_data_without_native_tooltips_or_static_tab_stops(self):
        self.activity.summary = 'Full summary ' * 30
        self.activity.description = 'Full description ' * 80
        self.activity.save()
        html = self.client.get(reverse('activities:index')).content.decode()
        card = html.split('id="participation-', 1)[1].split('activity-card__band-5', 1)[0]
        self.assertNotIn(' title="', card)
        self.assertNotIn('tabindex="0"', card)
        self.assertIn('data-full-text="Paddling together"', card)
        self.assertIn('>' + self.activity.summary + '</p>', card)
        self.assertIn('>' + self.activity.description + '</p>', card)
        # The natural navigation target remains a link even without JavaScript.
        self.assertIn('class="activity-card__title-link"', card)
