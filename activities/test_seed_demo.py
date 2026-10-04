from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template.defaultfilters import slugify
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from media_assets.models import ImageAsset, ImageAssetPurpose
from social.models import FriendGroup, FriendGroupMembership, Friendship, UserProfile

from .management.commands.seed_demo import ACTIVITY_DATA, CATEGORIES
from .models import Activity, ActivityCategory, ActivityResponse, ActivityResponseStatus, DemoSeedRecord


@override_settings(
    ENVIRONMENT="test",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class DemoSeedingTests(TestCase):
    def seed(self):
        call_command("seed_demo", stdout=StringIO())

    def first_demo_activity(self):
        key = f"activity:{slugify(ACTIVITY_DATA[0]['title'])}"
        return DemoSeedRecord.objects.get(key=key).content_object

    def record_ids(self):
        models = (
            get_user_model(), UserProfile, Activity, ActivityCategory, ActivityResponse,
            Friendship, FriendGroup, FriendGroupMembership, ImageAsset, DemoSeedRecord,
        )
        return {model: set(model.objects.values_list("pk", flat=True)) for model in models}

    def test_seeding_empty_database_creates_representative_records_and_local_logins(self):
        self.seed()

        self.assertEqual(Activity.objects.count(), len(ACTIVITY_DATA))
        self.assertEqual(ActivityCategory.objects.count(), len(CATEGORIES))
        self.assertEqual(ActivityResponse.objects.count(), len(ACTIVITY_DATA))
        self.assertEqual(Friendship.objects.count(), 5)
        self.assertEqual(FriendGroup.objects.count(), 3)
        self.assertEqual(FriendGroupMembership.objects.count(), 5)
        self.assertTrue(ImageAsset.objects.exists())
        self.assertTrue(Activity.objects.filter(starts_at__isnull=True).exists())
        self.assertTrue(Activity.objects.filter(starts_at__isnull=False).exists())
        self.assertTrue(Activity.objects.filter(multiple_events=True).exists())
        self.assertTrue(self.client.login(username="belong_demo", password="demo123"))
        self.assertTrue(self.client.login(username="belong_demo_admin", password="admin123"))
        admin = get_user_model().objects.get(username="belong_demo_admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_second_run_preserves_record_ids_passwords_privileges_and_responses(self):
        self.seed()
        original_ids = self.record_ids()
        admin = get_user_model().objects.get(username="belong_demo_admin")
        admin.set_password("changed-local-password")
        admin.is_superuser = False
        admin.save()
        original_password = admin.password
        response = ActivityResponse.objects.filter(activity=self.first_demo_activity()).get()
        response.status = ActivityResponseStatus.QUESTION
        response.note = "Keep this review note."
        response.save()

        self.seed()

        self.assertEqual(self.record_ids(), original_ids)
        admin.refresh_from_db()
        self.assertEqual(admin.password, original_password)
        self.assertFalse(admin.is_superuser)
        response.refresh_from_db()
        self.assertEqual(response.status, ActivityResponseStatus.QUESTION)
        self.assertEqual(response.note, "Keep this review note.")

    def test_unrelated_accounts_activities_categories_and_uploaded_images_survive_unchanged(self):
        # Legacy account names and matching titles/filenames must not imply seed ownership.
        user = get_user_model().objects.create_user(username="admin", password="private-password")
        profile = user.profile
        profile.status_text = "Personal status"
        profile.is_visible = False
        profile.save()
        category = ActivityCategory.objects.create(name="My Play", slug="play")
        asset = ImageAsset.objects.create(
            name="Personal upload", purpose=ImageAssetPurpose.ORGANIZER,
            filename="img/organizers/jonas.png", data=b"private uploaded content",
            content_type="image/png", size=24,
        )
        activity = Activity.objects.create(
            host=user, title=ACTIVITY_DATA[0]["title"], description="Personal activity",
            category=category, organizer_image=asset,
        )
        response = ActivityResponse.objects.create(
            activity=activity, user=user, status=ActivityResponseStatus.QUESTION, note="Personal note",
        )
        objects = (user, profile, category, asset, activity, response)
        originals = [type(obj).objects.filter(pk=obj.pk).values().get() for obj in objects]

        self.seed()
        self.seed()

        for obj, original in zip(objects, originals):
            with self.subTest(model=type(obj).__name__):
                self.assertEqual(type(obj).objects.filter(pk=obj.pk).values().get(), original)
        self.assertEqual(Activity.objects.count(), len(ACTIVITY_DATA) + 1)

    def test_untracked_activity_created_by_demo_account_is_preserved(self):
        self.seed()
        demo_host = self.first_demo_activity().host
        activity = Activity.objects.create(
            host=demo_host, title=ACTIVITY_DATA[0]["title"], description="Manually created during review",
        )
        original = Activity.objects.filter(pk=activity.pk).values().get()

        self.seed()

        self.assertEqual(Activity.objects.filter(pk=activity.pk).values().get(), original)
        self.assertEqual(Activity.objects.count(), len(ACTIVITY_DATA) + 1)

    def test_known_demo_activity_can_be_refreshed_without_replacement(self):
        self.seed()
        activity = self.first_demo_activity()
        activity.description = "Temporary demo edit"
        activity.save()

        self.seed()

        activity.refresh_from_db()
        self.assertEqual(activity.description, ACTIVITY_DATA[0]["description"])
        self.assertEqual(Activity.objects.count(), len(ACTIVITY_DATA))

    def test_conflicting_account_is_preserved_and_entire_seed_rolls_back(self):
        user = get_user_model().objects.create_user(username="belong_demo", password="personal-password")
        original = get_user_model().objects.filter(pk=user.pk).values().get()

        with self.assertRaisesMessage(CommandError, "Existing data conflicts"):
            self.seed()

        self.assertEqual(get_user_model().objects.filter(pk=user.pk).values().get(), original)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(DemoSeedRecord.objects.exists())
        self.assertFalse(Activity.objects.exists())

    def test_reassigned_demo_activity_is_not_overwritten(self):
        self.seed()
        user = get_user_model().objects.create_user(username="owner")
        activity = self.first_demo_activity()
        activity.host = user
        activity.save()
        original = Activity.objects.filter(pk=activity.pk).values().get()

        with self.assertRaisesMessage(CommandError, "owner changed"):
            self.seed()

        self.assertEqual(Activity.objects.filter(pk=activity.pk).values().get(), original)

    def test_seeded_records_render_in_current_index_and_detail_views(self):
        self.seed()
        self.client.force_login(get_user_model().objects.get(username="belong_demo"))
        index = self.client.get(reverse("activities:index"))
        self.assertEqual(index.status_code, 200)
        self.assertTemplateUsed(index, "activities/index.html")
        self.assertEqual(len(index.context["activities"]), len(ACTIVITY_DATA))
        for activity in Activity.objects.all():
            with self.subTest(activity=activity.title):
                self.assertContains(index, activity.title)
                detail = self.client.get(reverse("activities:detail", args=[activity.pk]))
                self.assertEqual(detail.status_code, 200)
                self.assertTemplateUsed(detail, "activities/detail.html")
                self.assertContains(detail, escape(activity.description))
                if activity.header_image:
                    image = self.client.get(activity.header_image.get_absolute_url())
                    self.assertEqual(image.status_code, 200)
                    self.assertEqual(image.content, bytes(activity.header_image.data))

    @override_settings(ENVIRONMENT="production")
    def test_production_seeding_is_rejected_before_writing_records(self):
        with self.assertRaisesMessage(CommandError, "only in local dev/test"):
            self.seed()

        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(DemoSeedRecord.objects.exists())
