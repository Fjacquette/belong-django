from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from groups.models import Group, GroupMembership
from media_assets.models import ImageAsset
from .forms import ActivityForm
from .models import Activity, ActivitySeries
from .series import occurrence_initial


class ActivitySeriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.owner = U.objects.create_user('series-owner')
        cls.other = U.objects.create_user('series-other')
        buffer = BytesIO(); Image.new('RGB', (10, 10), 'teal').save(buffer, format='PNG')
        data = buffer.getvalue()
        cls.images = [ImageAsset.objects.create(name=f'Artwork {n}', purpose='activity_header', data=data, content_type='image/png', size=len(data)) for n in range(3)]
        cls.group = Group.objects.create(name='Private hiking group', owner=cls.owner, access='private', default_activity_image=cls.images[0])
        GroupMembership.objects.create(group=cls.group, user=cls.owner, role='organizer')
        cls.series = ActivitySeries.objects.create(owner=cls.owner, group=cls.group, title='Weekend Hikes', description='Hike together',
                                                  location_type='in_person', location_name='Creek trail', location_gps='40,-75',
                                                  cost_type='paid', cost_amount=Decimal('5.00'), cost_display='$5',
                                                  cadence='weekly', weekday=5, available_responses=['committed', 'question'])

    def setUp(self):
        self.client.force_login(self.owner)

    def occurrence_url(self, series=None):
        return reverse('activities:create') + f'?series={(series or self.series).pk}'

    def post_occurrence(self, **overrides):
        data = {k: ('' if v is None else v) for k, v in occurrence_initial(self.series).items()}
        data.update(overrides)
        return self.client.post(self.occurrence_url(), data)

    def test_group_series_creation_and_flexible_series_without_group(self):
        url = reverse('activities:series_create') + f'?group={self.group.pk}'
        page = self.client.get(url)
        self.assertTrue(page.context['form'].fields['group'].disabled)
        self.assertNotContains(page, 'aria-label="Create"')
        self.assertContains(page, 'For Private hiking group')
        self.assertContains(page, 'class="ui-choice-list"')
        self.assertContains(page, 'value="committed" class="ui-check"')
        for path, group, cadence in [(url, self.group, 'weekly'), (reverse('activities:series_create'), None, 'flexible')]:
            response = self.client.post(path, {'title': 'New pattern', 'description': 'Reusable activity', 'cadence': cadence,
                                             'location_type': 'tbd', 'audience': 'everyone', 'cost_type': 'free', 'group': ''})
            series = ActivitySeries.objects.latest('pk')
            self.assertRedirects(response, series.get_absolute_url())
            self.assertEqual(series.group, group)
            self.assertEqual(series.cadence, cadence)
            self.assertEqual(series.owner, self.owner)
            self.assertEqual(series.available_responses, ['interested'])

    def test_inherited_fields_can_be_overridden_and_occurrence_is_discoverable(self):
        page = self.client.get(self.occurrence_url())
        self.assertContains(page, 'From series:')
        self.assertContains(page, 'Weekend Hikes')
        self.assertContains(self.client.get(reverse('activities:create')), f'?series={self.series.pk}')
        self.assertEqual(page.context['form'].initial['location_name'], 'Creek trail')
        self.assertEqual(page.context['form'].initial['available_responses'], ['committed', 'question'])
        self.assertIsNone(page.context['form'].initial.get('starts_at'))
        response = self.post_occurrence(title='Specific Saturday hike', location_name='Different trail',
                                        starts_at='2026-10-10T09:00', available_responses=['interested'], audience='everyone')
        activity = Activity.objects.latest('pk')
        self.assertRedirects(response, reverse('activities:detail', args=[activity.pk]))
        self.assertEqual(activity.series, self.series)
        self.assertEqual(activity.group, self.group)
        self.assertEqual(activity.location_name, 'Different trail')
        self.assertEqual(activity.cost_amount, Decimal('5.00'))
        self.assertEqual(activity.header_image, self.images[0])
        self.assertEqual(activity.available_responses, ['interested'])
        self.assertEqual(activity.audience, 'everyone')
        self.assertContains(self.client.get(reverse('activities:index')), 'Specific Saturday hike')

    def test_activity_series_group_image_precedence(self):
        # Series blank -> group, series supplied -> series, occurrence supplied -> occurrence.
        self.post_occurrence(header_image='')
        self.assertEqual(Activity.objects.latest('pk').header_image, self.images[0])
        self.series.header_image = self.images[1]; self.series.save()
        self.post_occurrence(header_image='')
        self.assertEqual(Activity.objects.latest('pk').header_image, self.images[1])
        self.post_occurrence(header_image=str(self.images[2].pk))
        self.assertEqual(Activity.objects.latest('pk').header_image, self.images[2])

    def test_changed_defaults_do_not_rewrite_occurrences_or_shared_lists(self):
        self.post_occurrence()
        activity = Activity.objects.latest('pk')
        original = (activity.title, activity.location_name, activity.header_image_id, activity.available_responses)
        data = {k: ('' if v is None else v) for k, v in occurrence_initial(self.series).items()}
        data.update(title='Changed series', location_name='Another trail', cadence='monthly', header_image=str(self.images[1].pk), available_responses=['vote'])
        self.client.post(reverse('activities:series_edit', args=[self.series.pk]), data)
        self.series.refresh_from_db()
        self.assertEqual(self.series.title, 'Changed series')
        self.group.default_activity_image = self.images[2]; self.group.save()
        activity.refresh_from_db()
        self.assertEqual((activity.title, activity.location_name, activity.header_image_id, activity.available_responses), original)
        initial = occurrence_initial(self.series)
        initial['available_responses'].append('question')
        self.assertEqual(self.series.available_responses, ['vote'])

    def test_organizer_authority_and_private_context_not_leaked(self):
        self.client.force_login(self.other)
        for path in [self.series.get_absolute_url(), reverse('activities:series_edit', args=[self.series.pk]), self.occurrence_url(),
                     reverse('activities:series_create') + f'?group={self.group.pk}']:
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, {}).status_code, 404)
        self.client.force_login(self.owner); self.post_occurrence()
        activity = Activity.objects.latest('pk')
        self.client.force_login(self.other)
        page = self.client.get(reverse('activities:detail', args=[activity.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, self.group.name)
        self.assertNotContains(page, self.series.get_absolute_url())
        GroupMembership.objects.create(group=self.group, user=self.other, role='organizer')
        self.assertEqual(self.client.get(self.occurrence_url()).status_code, 200)

    def test_occurrence_cannot_switch_series_group_or_forge_series_assignment(self):
        other = Group.objects.create(name='Other organized group', owner=self.owner)
        self.assertEqual(self.client.get(self.occurrence_url() + f'&group={other.pk}').status_code, 404)
        self.post_occurrence(group=other.pk, series='999')
        activity = Activity.objects.latest('pk')
        self.assertEqual(activity.group, self.group)
        self.assertEqual(activity.series, self.series)
        self.client.post(reverse('activities:create'), {'title': 'Ordinary', 'description': 'Independent', 'audience': 'everyone',
                          'cost_type': 'free', 'location_type': 'tbd', 'series': self.series.pk})
        self.assertIsNone(Activity.objects.latest('pk').series_id)

    def test_shared_validation_rejects_invalid_cost_gps_and_choices(self):
        data = {'title': 'Invalid pattern', 'description': 'Test', 'cadence': 'weekly', 'audience': 'everyone',
                'location_type': 'in_person', 'location_gps': 'invalid', 'cost_type': 'free', 'cost_amount': '5',
                'available_responses': ['invented']}
        page = self.client.post(reverse('activities:series_create'), data)
        self.assertContains(page, 'Use latitude, longitude')
        self.assertContains(page, 'A free activity must have a zero cost')
        self.assertEqual(ActivitySeries.objects.count(), 1)

    def test_series_deletion_preserves_normal_activity_and_copied_values(self):
        self.post_occurrence()
        activity = Activity.objects.latest('pk')
        self.series.delete(); activity.refresh_from_db()
        self.assertIsNone(activity.series_id)
        self.assertEqual(activity.group, self.group)
        self.assertEqual(activity.title, 'Weekend Hikes')
