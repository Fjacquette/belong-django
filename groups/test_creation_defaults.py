from belong.test_helpers import create_legacy_user
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from media_assets.models import ImageAsset
from .models import Group, GroupMembership


def upload(name='art.png'):
    output = BytesIO()
    Image.new('RGB', (20, 20), 'purple').save(output, format='PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


class GroupCreationDefaultsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_legacy_user('defaults-owner')
        cls.other = create_legacy_user('defaults-other')
        data = upload().read()
        cls.art = ImageAsset.objects.create(name='Group activity artwork', purpose='activity_header', data=data, size=len(data), content_type='image/png')
        cls.override = ImageAsset.objects.create(name='Specific artwork', purpose='activity_header', data=data, size=len(data), content_type='image/png')
        cls.avatar = ImageAsset.objects.create(name='Group identity', purpose='group_image', data=data, size=len(data), content_type='image/png')
        cls.group = Group.objects.create(name='West Chester Hikes', owner=cls.owner, access='private', image=cls.avatar, default_activity_image=cls.art)
        GroupMembership.objects.create(group=cls.group, user=cls.owner, role='organizer')

    def setUp(self):
        self.client.force_login(self.owner)

    def activity_data(self, **extra):
        return {'title': 'Saturday hike', 'description': 'Walk together', 'location_type': 'in_person',
                'audience': 'everyone', 'cost_type': 'free', **extra}

    def test_focused_forms_and_descriptive_native_access_choices(self):
        for route in ['groups:create', 'activities:create']:
            page = self.client.get(reverse(route))
            self.assertNotContains(page, 'aria-label="Create"')
        page = self.client.get(reverse('groups:create'))
        self.assertContains(page, 'Who can find and join this group?')
        self.assertContains(page, 'type="radio"', count=4)
        self.assertContains(page, 'an organizer must approve new members')
        self.assertContains(page, 'join by invitation only')
        self.assertNotContains(page, '<select name="access"')
        self.assertContains(self.client.get(reverse('activities:index')), 'aria-label="Create"')

    def test_group_uploads_have_distinct_purposes_and_edit_does_not_rewrite_activity(self):
        response = self.client.post(reverse('groups:create'), {'name': 'New hikers', 'access': 'closed',
                                    'image_upload': upload('identity.png'), 'default_activity_image_upload': upload('default.png')})
        group = Group.objects.get(name='New hikers')
        self.assertRedirects(response, group.get_absolute_url())
        self.assertEqual(group.image.purpose, 'group_image')
        self.assertEqual(group.default_activity_image.purpose, 'activity_header')
        self.client.post(reverse('activities:create') + f'?group={group.pk}', self.activity_data())
        activity = Activity.objects.latest('pk')
        old_image = activity.header_image_id
        self.client.post(reverse('groups:edit', args=[group.pk]), {'name': group.name, 'access': group.access,
                         'image': str(group.image_id), 'default_activity_image_upload': upload('new-default.png')})
        group.refresh_from_db(); activity.refresh_from_db()
        self.assertNotEqual(group.default_activity_image_id, old_image)
        self.assertEqual(activity.header_image_id, old_image)
        self.assertIsNone(activity.organizer_image_id)

    def test_invalid_upload_does_not_save_group_or_assets(self):
        before = ImageAsset.objects.count()
        page = self.client.post(reverse('groups:create'), {'name': 'Invalid', 'access': 'open',
                                'image_upload': SimpleUploadedFile('fake.png', b'<script>bad</script>')})
        self.assertContains(page, 'Upload a valid')
        self.assertFalse(Group.objects.filter(name='Invalid').exists())
        self.assertEqual(ImageAsset.objects.count(), before)

    def test_group_context_is_visible_locked_and_copies_default(self):
        url = reverse('activities:create') + f'?group={self.group.pk}'
        page = self.client.get(url)
        self.assertContains(page, 'Creating an activity for West Chester Hikes')
        self.assertTrue(page.context['form'].fields['group'].disabled)
        self.assertEqual(page.context['form'].initial['header_image'], self.art.pk)
        self.client.post(url, self.activity_data(group=''))
        activity = Activity.objects.latest('pk')
        self.assertEqual(activity.group, self.group)
        self.assertEqual(activity.header_image, self.art)
        self.assertEqual(activity.audience, 'everyone')
        self.assertIsNone(activity.organizer_image_id)
        self.assertEqual(activity.host, self.owner)

    def test_global_group_selection_and_override_and_independent_activity(self):
        page = self.client.get(reverse('activities:create'))
        self.assertContains(page, 'For a group?')
        self.assertIn(str(self.group.pk), page.context['group_defaults'])
        for extra, image, group in [({}, None, None), ({'group': self.group.pk}, self.art, self.group),
                                   ({'group': self.group.pk, 'header_image': str(self.override.pk)}, self.override, self.group)]:
            self.client.post(reverse('activities:create'), self.activity_data(**extra))
            activity = Activity.objects.latest('pk')
            self.assertEqual(activity.header_image, image)
            self.assertEqual(activity.group, group)

    def test_nonorganizers_cannot_select_context_edit_or_see_private_identity_image(self):
        self.client.force_login(self.other)
        for path in [reverse('activities:create') + f'?group={self.group.pk}', reverse('groups:edit', args=[self.group.pk]), self.avatar.get_absolute_url()]:
            self.assertEqual(self.client.get(path).status_code, 404)
        page = self.client.get(reverse('activities:create'))
        self.assertNotContains(page, self.group.name)
        page = self.client.post(reverse('activities:create'), self.activity_data(group=self.group.pk))
        self.assertEqual(page.status_code, 200)
        self.assertFalse(Activity.objects.exists())
        GroupMembership.objects.create(group=self.group, user=self.other)
        self.assertEqual(self.client.get(self.avatar.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse('groups:edit', args=[self.group.pk])).status_code, 404)
