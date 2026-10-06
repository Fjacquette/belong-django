from io import BytesIO

from PIL import Image
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from belong.test_helpers import create_legacy_user
from media_assets.models import ImageAsset
from .models import Activity


class IdentityQueryTests(TestCase):
    def test_discover_queries_do_not_grow_per_host_profile_or_hidden_card(self):
        viewer = create_legacy_user('query-viewer')
        self.client.force_login(viewer)
        buffer = BytesIO(); Image.new('RGB', (2, 2), 'red').save(buffer, format='PNG')
        asset = ImageAsset.objects.create(name='Avatar', data=buffer.getvalue(), size=len(buffer.getvalue()), content_type='image/png', purpose='profile_avatar')
        def add_card(n):
            host = create_legacy_user(f'query-host-{n}')
            host.profile.avatar_image = asset
            host.profile.display_name = f'Host {n}'
            host.profile.save()
            Activity.objects.create(title=f'Card {n}', description='Query fixture', host=host)
        add_card(0)
        # Warm session and the throttled presence timestamp outside the measurement.
        self.client.get(reverse('activities:index'))
        with CaptureQueriesContext(connection) as single:
            self.client.get(reverse('activities:index'))
        for n in range(1, 12): add_card(n)
        with CaptureQueriesContext(connection) as many:
            response = self.client.get(reverse('activities:index'))
        self.assertEqual(len(response.context['activities']), 12)
        self.assertEqual(len(many), len(single))
        self.assertFalse(any('COUNT(' in q['sql'] and 'GROUP BY' in q['sql'] for q in many.captured_queries))
