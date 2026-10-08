from belong.test_helpers import create_legacy_user
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Activity,
    ActivityLocationType,
    ActivityResponse,
    ActivityResponseStatus,
    ActivityVisibility,
)


class ActivityLoopTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.host = create_legacy_user(username="host")
        cls.participant = create_legacy_user(username="participant")
        cls.other_user = create_legacy_user(username="other")
        cls.activity = Activity.objects.create(
            host=cls.host,
            title="Walk together",
            description="Find a time for a walk in the park.",
            available_responses=["more", "committed", "question"],
        )

    def setUp(self):
        self.client.force_login(self.participant)

    def test_anonymous_users_are_redirected_to_login_without_changing_data(self):
        self.client.logout()
        existing = ActivityResponse.objects.create(
            user=self.participant,
            activity=self.activity,
            status=ActivityResponseStatus.QUESTION,
        )
        routes = [
            ("get", "index", {}),
            ("get", "categories", {}),
            ("get", "detail", {"pk": self.activity.pk}),
            ("get", "create", {}),
            ("post", "create", {}),
            ("post", "respond", {"pk": self.activity.pk}),
            ("post", "join", {"pk": self.activity.pk}),
            ("post", "leave", {"pk": self.activity.pk}),
        ]
        for method, name, kwargs in routes:
            with self.subTest(method=method, route=name):
                url = reverse(f"activities:{name}", kwargs=kwargs)
                data = {
                    "title": "Anonymous activity",
                    "description": "An anonymous user must not be able to create this.",
                    "location_type": ActivityLocationType.TBD,
                    "audience": ActivityVisibility.EVERYONE,
                    "status": ActivityResponseStatus.COMMITTED,
                } if method == "post" else {}
                response = getattr(self.client, method)(url, data)
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )
                self.assertEqual(Activity.objects.count(), 1)
                self.assertEqual(ActivityResponse.objects.count(), 1)
                existing.refresh_from_db()
                self.assertEqual(existing.status, ActivityResponseStatus.QUESTION)

    def test_authenticated_user_can_load_index(self):
        response = self.client.get(reverse("activities:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "activities/index.html")
        self.assertContains(response, self.activity.title)
        self.assertEqual(
            [activity.pk for activity in response.context["activities"]], [self.activity.pk]
        )

    def test_authenticated_user_can_load_detail(self):
        response = self.client.get(reverse("activities:detail", args=[self.activity.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "activities/detail.html")
        self.assertContains(response, self.activity.title)
        self.assertContains(response, self.activity.description)
        self.assertEqual(response.context["activity"].pk, self.activity.pk)

    def test_authenticated_user_can_load_creation_form(self):
        response = self.client.get(reverse("activities:create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "activities/form.html")

    def test_creating_basic_activity_assigns_current_user_as_host(self):
        response = self.client.post(
            reverse("activities:create"),
            {
                "title": "Play a board game",
                "cost_type": "unknown",
                "description": "Choose a game and a time together.",
                "location_type": ActivityLocationType.TBD,
                "audience": ActivityVisibility.EVERYONE,
                "host": self.host.pk,
            },
        )

        self.assertEqual(Activity.objects.count(), 2)
        created = Activity.objects.get(title="Play a board game")
        self.assertEqual(created.host_id, self.participant.pk)
        self.assertEqual(created.description, "Choose a game and a time together.")
        self.assertIsNone(created.starts_at)
        self.assertIsNone(created.ends_at)
        self.assertEqual(created.available_responses, ["more"])
        self.assertEqual(created.active_responses(), ["more"])
        self.assertRedirects(response, reverse("activities:detail", args=[created.pk]))

    def test_allowed_response_statuses_are_stored(self):
        for status in (
            ActivityResponseStatus.MORE,
            ActivityResponseStatus.COMMITTED,
            ActivityResponseStatus.QUESTION,
        ):
            with self.subTest(status=status):
                response = self.client.post(
                    reverse("activities:respond", args=[self.activity.pk]),
                    {"status": status},
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "activities/_join_region.html")
                stored = ActivityResponse.objects.get(user=self.participant, activity=self.activity)
                self.assertEqual(stored.status, status)
                self.assertEqual(response.context["current_status"], status)
                self.assertTrue(response.context["joined"])
                ActivityResponse.objects.all().delete()

    def test_activity_can_explicitly_allow_declined_response(self):
        self.activity.available_responses = [ActivityResponseStatus.DECLINED]
        self.activity.save(update_fields=["available_responses"])

        response = self.client.post(
            reverse("activities:respond", args=[self.activity.pk]),
            {"status": ActivityResponseStatus.DECLINED},
        )

        self.assertEqual(response.status_code, 200)
        stored = ActivityResponse.objects.get(user=self.participant, activity=self.activity)
        self.assertEqual(stored.status, ActivityResponseStatus.DECLINED)

    def test_responding_again_updates_existing_response(self):
        url = reverse("activities:respond", args=[self.activity.pk])
        self.client.post(url, {"status": ActivityResponseStatus.MORE})
        original = ActivityResponse.objects.get(user=self.participant, activity=self.activity)

        response = self.client.post(url, {"status": ActivityResponseStatus.COMMITTED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ActivityResponse.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.status, ActivityResponseStatus.COMMITTED)
        self.assertEqual(response.context["current_status"], ActivityResponseStatus.COMMITTED)

    def test_invalid_or_disallowed_status_does_not_create_response(self):
        self.activity.available_responses = [ActivityResponseStatus.MORE]
        self.activity.save(update_fields=["available_responses"])
        for data in (
            {}, {"status": ""}, {"status": "invalid"},
            {"status": ActivityResponseStatus.COMMITTED},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("activities:respond", args=[self.activity.pk]), data
                )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(ActivityResponse.objects.exists())
                self.assertFalse(response.context["joined"])

    def test_invalid_or_disallowed_status_preserves_existing_response(self):
        self.activity.available_responses = [ActivityResponseStatus.MORE]
        self.activity.save(update_fields=["available_responses"])
        existing = ActivityResponse.objects.create(
            user=self.participant,
            activity=self.activity,
            status=ActivityResponseStatus.MORE,
        )
        for data in (
            {}, {"status": ""}, {"status": "invalid"},
            {"status": ActivityResponseStatus.COMMITTED},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("activities:respond", args=[self.activity.pk]), data
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(ActivityResponse.objects.count(), 1)
                existing.refresh_from_db()
                self.assertEqual(existing.status, ActivityResponseStatus.MORE)

    def test_default_responses_do_not_allow_declined(self):
        self.activity.available_responses = []
        self.activity.save(update_fields=["available_responses"])
        response = self.client.post(
            reverse("activities:respond", args=[self.activity.pk]),
            {"status": ActivityResponseStatus.DECLINED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActivityResponse.objects.exists())

    def test_responding_does_not_change_another_users_response(self):
        other_response = ActivityResponse.objects.create(
            user=self.other_user,
            activity=self.activity,
            status=ActivityResponseStatus.QUESTION,
            note="Can we bring a dog?",
        )
        url = reverse("activities:respond", args=[self.activity.pk])
        for status in (ActivityResponseStatus.MORE, ActivityResponseStatus.COMMITTED):
            with self.subTest(status=status):
                response = self.client.post(url, {"status": status, "user": self.other_user.pk})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(ActivityResponse.objects.count(), 2)
                stored = ActivityResponse.objects.get(user=self.participant, activity=self.activity)
                self.assertEqual(stored.status, status)
                other_response.refresh_from_db()
                self.assertEqual(other_response.status, ActivityResponseStatus.QUESTION)
                self.assertEqual(other_response.note, "Can we bring a dog?")

    def test_leaving_removes_only_current_users_response(self):
        own_response = ActivityResponse.objects.create(user=self.participant, activity=self.activity)
        other_response = ActivityResponse.objects.create(
            user=self.other_user, activity=self.activity, status=ActivityResponseStatus.QUESTION
        )
        response = self.client.post(
            reverse("activities:leave", args=[self.activity.pk]), {"user": self.other_user.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActivityResponse.objects.filter(pk=own_response.pk).exists())
        self.assertEqual(ActivityResponse.objects.get().pk, other_response.pk)
        other_response.refresh_from_db()
        self.assertEqual(other_response.status, ActivityResponseStatus.QUESTION)
        self.assertFalse(response.context["joined"])
        self.assertIsNone(response.context["current_status"])

    def test_leaving_without_a_response_is_harmless(self):
        response = self.client.post(reverse("activities:leave", args=[self.activity.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActivityResponse.objects.exists())

    def test_join_uses_first_creator_choice_without_duplicating_response(self):
        self.activity.available_responses = [
            ActivityResponseStatus.COMMITTED, ActivityResponseStatus.MORE,
        ]
        self.activity.save(update_fields=["available_responses"])
        url = reverse("activities:join", args=[self.activity.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        original = ActivityResponse.objects.get(user=self.participant, activity=self.activity)
        self.assertEqual(original.status, ActivityResponseStatus.COMMITTED)

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ActivityResponse.objects.count(), 1)
        self.assertEqual(ActivityResponse.objects.get().pk, original.pk)

    def test_response_actions_require_post_without_changing_data(self):
        existing = ActivityResponse.objects.create(
            user=self.participant, activity=self.activity, status=ActivityResponseStatus.QUESTION
        )
        for name in ("respond", "join", "leave"):
            with self.subTest(route=name):
                response = self.client.get(
                    reverse(f"activities:{name}", args=[self.activity.pk]),
                    {"status": ActivityResponseStatus.COMMITTED},
                )

                self.assertEqual(response.status_code, 405)
                self.assertEqual(ActivityResponse.objects.count(), 1)
                existing.refresh_from_db()
                self.assertEqual(existing.status, ActivityResponseStatus.QUESTION)
