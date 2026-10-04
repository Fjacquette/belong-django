from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Activity, ActivityResponse, ActivityResponseStatus


class ParticipationUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = get_user_model().objects.create_user(username="ui-host")
        cls.viewer = get_user_model().objects.create_user(username="ui-viewer")
        cls.activity = Activity.objects.create(
            host=cls.host, title="An open-ended walk", description="Find a time together",
            action1_label="Organizer website", action1_url="https://example.com/walk",
            action2_label="Route", action2_url="https://example.com/route",
        )

    def setUp(self):
        self.client.force_login(self.viewer)

    def url(self, name):
        return reverse(f"activities:{name}", args=[self.activity.pk])

    def test_allowed_choices_and_secondary_link_on_card_and_detail(self):
        self.activity.available_responses = ["interested", "question", "declined"]
        self.activity.save()
        for url in [reverse("activities:index"), self.url("detail")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                for status in self.activity.available_responses:
                    self.assertContains(response, f'value="{status}"')
                self.assertNotContains(response, 'value="committed"')
                self.assertContains(response, 'href="https://example.com/walk"')
                self.assertContains(response, f'hx-post="{self.url("respond")}"')
                self.assertContains(response, f'hx-target="#participation-{self.activity.pk}"')
                self.assertContains(response, 'hx-swap="outerHTML"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(self.client.get(reverse("activities:index")), f'href="{self.url("detail")}"')
        self.assertContains(self.client.get(self.url("detail")), 'href="https://example.com/route"')

    def test_htmx_select_change_and_remove_preserve_variant_and_other_users(self):
        ActivityResponse.objects.create(user=self.host, activity=self.activity, status="interested")
        for variant in ["card", "detail"]:
            for status in ["interested", "committed", "question"]:
                with self.subTest(variant=variant, status=status):
                    response = self.client.post(self.url("respond"), {"status": status, "variant": variant}, HTTP_HX_REQUEST="true")
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, '<html')
                    self.assertContains(response, f'id="participation-{self.activity.pk}"')
                    self.assertContains(response, f'You: {ActivityResponseStatus(status).label}')
                    self.assertContains(response, f'name="variant" value="{variant}"')
                    self.assertContains(response, f'hx-post="{self.url("leave")}"')
                    self.assertEqual(ActivityResponse.objects.get(user=self.viewer, activity=self.activity).status, status)
                    self.assertEqual(ActivityResponse.objects.filter(user=self.viewer).count(), 1)
                    for url in [reverse("activities:index"), self.url("detail")]:
                        self.assertContains(self.client.get(url), f'You: {ActivityResponseStatus(status).label}')
            response = self.client.post(self.url("leave"), {"variant": variant}, HTTP_HX_REQUEST="true")
            self.assertContains(response, "No response yet")
            self.assertFalse(ActivityResponse.objects.filter(user=self.viewer).exists())
            self.assertTrue(ActivityResponse.objects.filter(user=self.host).exists())

    def test_counts_distinguish_interest_from_commitment(self):
        ActivityResponse.objects.create(user=self.host, activity=self.activity, status="interested")
        response = self.client.post(self.url("respond"), {"variant": "detail", "status": "committed"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "1 interested · 1 count me in")
        self.assertContains(response, 'aria-pressed="true"', count=1)
        response = self.client.post(self.url("respond"), {"variant": "detail", "status": "question"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "1 interested · 0 count me in")

    def test_removed_choice_keeps_existing_response_visible_and_removable(self):
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="committed")
        self.activity.available_responses = ["interested"]
        self.activity.save()
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "You: Count me in")
        self.assertContains(response, "Remove response")
        response = self.client.post(self.url("respond"), {"variant": "detail", "status": "declined"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "You: Count me in")

    def test_invalid_configuration_shows_no_choices_but_allows_removal(self):
        self.activity.available_responses = ["unknown"]
        self.activity.save()
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="interested")
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "No response choices available.")
        self.assertNotContains(response, f'hx-post="{self.url("respond")}"')
        self.assertContains(response, f'hx-post="{self.url("leave")}"')

    def test_current_card_choice_is_selected(self):
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="committed")
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, '<option value="committed" selected>Count me in</option>', html=True)

    def test_plain_forms_redirect_back_to_full_page(self):
        for variant, destination in [("card", reverse("activities:index")), ("detail", self.url("detail"))]:
            for action in ["respond", "leave"]:
                response = self.client.post(self.url(action), {"variant": variant, "status": "interested"})
                self.assertRedirects(response, destination)

    def test_ui_posts_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.viewer)
        self.assertEqual(client.post(self.url("respond"), {"status": "interested", "variant": "card"}, HTTP_HX_REQUEST="true").status_code, 403)
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer).exists())
