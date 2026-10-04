from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from social.models import Friendship

from .admin import ActivityAdmin
from .forms import ActivityForm
from .models import (
    Activity, ActivityResponse, ActivityResponseStatus, ActivityVisibility, DEFAULT_RESPONSE_CHOICES,
)


class AudienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.host = User.objects.create_user(username="host")
        cls.friend = User.objects.create_user(username="friend")
        cls.extended = User.objects.create_user(username="extended")
        cls.third_degree = User.objects.create_user(username="third_degree")
        cls.outsider = User.objects.create_user(username="outsider")
        Friendship.make_pair(cls.host, cls.friend)
        Friendship.make_pair(cls.friend, cls.extended)
        Friendship.make_pair(cls.extended, cls.third_degree)
        cls.activities = {}
        for audience in [*ActivityVisibility.values, "unsupported"]:
            cls.activities[audience] = Activity.objects.create(
                host=cls.host, title=f"Private title {audience}",
                description=f"Private description {audience}",
                location_address1=f"Private address {audience}", audience=audience,
            )

    def allowed_audiences(self, viewer):
        if viewer == self.host:
            return set(self.activities)
        allowed = {ActivityVisibility.EVERYONE}
        if viewer == self.friend:
            allowed.add(ActivityVisibility.FRIENDS)
        if viewer in (self.friend, self.extended):
            allowed.add(ActivityVisibility.EXTENDED_FRIENDS)
        return allowed

    def test_index_and_detail_share_exact_audience_rule_and_do_not_render_private_data(self):
        for viewer in (self.host, self.friend, self.extended, self.third_degree, self.outsider):
            self.client.force_login(viewer)
            index = self.client.get(reverse("activities:index"))
            self.assertEqual(index.status_code, 200)
            allowed = self.allowed_audiences(viewer)
            for audience, activity in self.activities.items():
                with self.subTest(viewer=viewer.username, audience=audience):
                    detail = self.client.get(reverse("activities:detail", args=[activity.pk]))
                    if audience in allowed:
                        self.assertContains(index, activity.title)
                        self.assertContains(detail, activity.description)
                        self.assertContains(detail, activity.location_address1)
                    else:
                        self.assertEqual(detail.status_code, 404)
                        for text in (activity.title, activity.description, activity.location_address1):
                            self.assertNotContains(index, text)
                            self.assertNotContains(detail, text, status_code=404)

    def test_search_cannot_reveal_hidden_descriptions(self):
        self.client.force_login(self.outsider)
        activity = self.activities[ActivityVisibility.FRIENDS]
        response = self.client.get(reverse("activities:index"), {"q": activity.description})

        self.assertContains(response, "No activities yet")
        self.assertNotContains(response, activity.title)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_participation_outside_audience_returns_404_and_preserves_existing_responses(self):
        for viewer in (self.friend, self.extended, self.third_degree, self.outsider):
            self.client.force_login(viewer)
            for audience, activity in self.activities.items():
                if audience in self.allowed_audiences(viewer):
                    continue
                existing = ActivityResponse.objects.create(
                    user=viewer, activity=activity, status=ActivityResponseStatus.QUESTION,
                    note="A legacy response must not grant access.",
                )
                original = ActivityResponse.objects.filter(pk=existing.pk).values().get()
                for action in ("respond", "join", "leave"):
                    with self.subTest(viewer=viewer.username, audience=audience, action=action):
                        response = self.client.post(
                            reverse(f"activities:{action}", args=[activity.pk]),
                            {"status": ActivityResponseStatus.COMMITTED},
                        )
                        self.assertEqual(response.status_code, 404)
                        self.assertNotContains(response, activity.title, status_code=404)
                        self.assertNotContains(response, activity.description, status_code=404)
                        self.assertNotContains(response, activity.location_address1, status_code=404)
                        self.assertEqual(ActivityResponse.objects.filter(pk=existing.pk).values().get(), original)

    def test_allowed_viewers_can_respond_join_and_leave(self):
        for viewer in (self.host, self.friend, self.extended, self.outsider):
            self.client.force_login(viewer)
            for audience in self.allowed_audiences(viewer):
                activity = self.activities[audience]
                with self.subTest(viewer=viewer.username, audience=audience):
                    for action in ("respond", "join"):
                        response = self.client.post(
                            reverse(f"activities:{action}", args=[activity.pk]),
                            {"status": ActivityResponseStatus.INTERESTED},
                        )
                        self.assertEqual(response.status_code, 200)
                        self.assertTemplateUsed(response, "activities/_join_region.html")
                        self.assertEqual(
                            ActivityResponse.objects.get(user=viewer, activity=activity).status,
                            ActivityResponseStatus.INTERESTED,
                        )
                    response = self.client.post(reverse("activities:leave", args=[activity.pk]))
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(ActivityResponse.objects.filter(user=viewer, activity=activity).exists())

    def test_friendships_are_symmetric_for_visibility(self):
        activity = Activity.objects.create(
            host=self.friend, title="Friend hosts instead", description="Reverse direction",
            audience=ActivityVisibility.FRIENDS,
        )
        self.client.force_login(self.host)
        self.assertContains(self.client.get(reverse("activities:index")), activity.title)
        self.assertContains(self.client.get(reverse("activities:detail", args=[activity.pk])), activity.description)

    def test_creation_form_rejects_and_does_not_offer_unbacked_audiences(self):
        self.client.force_login(self.host)
        page = self.client.get(reverse("activities:create"))
        request = RequestFactory().get("/admin/")
        request.user = self.host
        admin_form = ActivityAdmin(Activity, admin.site).get_form(request)
        admin_audiences = {value for value, label in admin_form().fields["audience"].choices}
        for audience in (ActivityVisibility.GROUP, ActivityVisibility.CUSTOM):
            with self.subTest(audience=audience):
                self.assertNotContains(page, f'value="{audience}"')
                self.assertNotIn(audience, admin_audiences)
                count = Activity.objects.count()
                response = self.client.post(reverse("activities:create"), {
                    "title": "Unsupported", "description": "Not ready", "location_type": "tbd",
                    "audience": audience,
                })
                self.assertContains(response, "Select a valid choice")
                self.assertEqual(Activity.objects.count(), count)


class ActionAndResponseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="participant")
        cls.activity = Activity.objects.create(host=cls.user, title="Activity", description="Description")

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, **overrides):
        return {
            "title": "New activity", "description": "Basic activity", "location_type": "tbd",
            "audience": "everyone", "host": self.user.pk, **overrides,
        }

    def test_forms_model_and_admin_reject_unsafe_action_urls(self):
        request = RequestFactory().get("/admin/")
        request.user = self.user
        admin_form = ActivityAdmin(Activity, admin.site).get_form(request)
        for field in ("action1_url", "action2_url", "action3_url"):
            for url in (
                "javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<script>alert(1)</script>",
                "ftp://example.com/file", "mailto:person@example.com", "//example.com", "/relative", "#",
            ):
                with self.subTest(field=field, url=url):
                    for form_class in (ActivityForm, admin_form):
                        form = form_class(data=self.data(**{field: url}))
                        self.assertFalse(form.is_valid())
                        self.assertIn(field, form.errors)
                    setattr(self.activity, field, url)
                    with self.assertRaises(ValidationError) as error:
                        self.activity.full_clean()
                    self.assertIn(field, error.exception.message_dict)
                    setattr(self.activity, field, "")

    def test_http_https_and_blank_action_urls_are_valid(self):
        for url in ("http://example.com/path", "https://example.com/path?q=1", ""):
            with self.subTest(url=url):
                form = ActivityForm(data=self.data(action1_url=url, action2_url=url, action3_url=url))
                self.assertTrue(form.is_valid(), form.errors)
                for field in ("action1_url", "action2_url", "action3_url"):
                    setattr(self.activity, field, url)
                self.activity.full_clean()

    def test_legacy_unsafe_urls_are_not_rendered_as_links(self):
        self.activity.action1_label = "First action"
        self.activity.action2_label = "Second action"
        self.activity.action3_label = "Third action"
        self.activity.action1_url = "javascript:alert(1)"
        self.activity.action2_url = "data:text/html,danger"
        self.activity.action3_url = "ftp://example.com/file"
        self.activity.save()  # Simulate legacy data that bypassed validation.
        for url in (reverse("activities:index"), reverse("activities:detail", args=[self.activity.pk])):
            response = self.client.get(url)
            self.assertContains(response, 'href="#"')
            for unsafe in ("javascript:", "data:text/html", "ftp://"):
                self.assertNotContains(response, unsafe)

    def test_safe_action_link_is_rendered(self):
        self.activity.action1_label = "Read more"
        self.activity.action1_url = "https://example.com/read"
        self.activity.save()
        response = self.client.get(reverse("activities:detail", args=[self.activity.pk]))
        self.assertContains(response, 'href="https://example.com/read"')

    def test_form_defaults_match_model_defaults_and_do_not_add_declined(self):
        form = ActivityForm()
        self.assertEqual(form.fields["available_responses"].initial, list(DEFAULT_RESPONSE_CHOICES))
        bound = ActivityForm(data=self.data())
        self.assertTrue(bound.is_valid(), bound.errors)
        activity = bound.save(commit=False)
        activity.host = self.user
        activity.save()
        self.assertEqual(activity.active_responses(), self.activity.active_responses())
        self.assertNotIn(ActivityResponseStatus.DECLINED, activity.active_responses())

    def test_join_prefers_interested_then_committed_regardless_of_order(self):
        for choices, expected in (
            (["declined", "committed", "interested"], "interested"),
            (["declined", "question", "committed"], "committed"),
        ):
            with self.subTest(choices=choices):
                self.activity.available_responses = choices
                self.activity.save()
                response = self.client.post(reverse("activities:join", args=[self.activity.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(ActivityResponse.objects.get(activity=self.activity, user=self.user).status, expected)

    def test_join_without_participation_option_does_not_create_or_change_response(self):
        for choices in (["declined"], ["question"], ["declined", "question"], ["invalid"], "interested", 42):
            self.activity.available_responses = choices
            self.activity.save()
            with self.subTest(choices=choices):
                url = reverse("activities:join", args=[self.activity.pk])
                self.assertEqual(self.client.post(url).status_code, 200)
                self.assertFalse(ActivityResponse.objects.exists())
                existing = ActivityResponse.objects.create(
                    activity=self.activity, user=self.user, status=ActivityResponseStatus.QUESTION
                )
                self.assertEqual(self.client.post(url).status_code, 200)
                existing.refresh_from_db()
                self.assertEqual(existing.status, ActivityResponseStatus.QUESTION)
                existing.delete()

    def test_retired_importer_cannot_mutate_data_even_with_reset(self):
        original = Activity.objects.filter(pk=self.activity.pk).values().get()
        with self.assertRaisesMessage(CommandError, "retired"):
            call_command("import_mock_activities", reset=True, stdout=StringIO())
        self.assertEqual(Activity.objects.filter(pk=self.activity.pk).values().get(), original)
        self.assertEqual(Activity.objects.count(), 1)
