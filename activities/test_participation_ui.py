from html import escape

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
            available_responses=["interested", "committed", "question"],
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
                choices = self.activity.available_responses if url == self.url("detail") else ["interested", "question"]
                for status in choices:
                    self.assertContains(response, f'value="{status}"')
                self.assertNotContains(response, 'value="committed"')
                if url != self.url("detail"):
                    self.assertNotContains(response, 'value="declined"')
                    self.assertNotContains(response, '<select id="response-')
                    self.assertNotContains(response, '>Save</button>')
                self.assertContains(response, 'href="https://example.com/walk"')
                self.assertContains(response, f'hx-post="{self.url("respond")}"')
                self.assertContains(response, f'hx-target="#participation-{self.activity.pk}"')
                self.assertContains(response, 'hx-swap="outerHTML"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(self.client.get(reverse("activities:index")), f'href="{self.url("detail")}"')
        self.assertContains(self.client.get(self.url("detail")), 'href="https://example.com/route"')

    def test_htmx_direct_change_and_remove_preserve_variant_and_other_users(self):
        ActivityResponse.objects.create(user=self.host, activity=self.activity, status="interested")
        for variant in ["card", "detail"]:
            for status in ["interested", "committed", "question"]:
                with self.subTest(variant=variant, status=status):
                    response = self.client.post(self.url("respond"), {"status": status, "variant": variant}, HTTP_HX_REQUEST="true")
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, '<html')
                    self.assertContains(response, f'id="participation-{self.activity.pk}"')
                    if variant == "detail":
                        self.assertContains(response, f'You: {ActivityResponseStatus(status).label}')
                    elif status in ["interested", "committed"]:
                        self.assertContains(response, f'value="{status}" aria-pressed="true"')
                    else:
                        self.assertNotContains(response, 'aria-pressed="true"')
                        self.assertContains(response, f'>You: {ActivityResponseStatus(status).label}</p>')
                    self.assertContains(response, f'name="variant" value="{variant}"')
                    self.assertContains(response, f'hx-post="{self.url("leave")}"')
                    self.assertEqual(ActivityResponse.objects.get(user=self.viewer, activity=self.activity).status, status)
                    self.assertEqual(ActivityResponse.objects.filter(user=self.viewer).count(), 1)
                    self.assertContains(self.client.get(self.url("detail")), f'You: {ActivityResponseStatus(status).label}')
            response = self.client.post(self.url("leave"), {"variant": variant}, HTTP_HX_REQUEST="true")
            if variant == "detail":
                self.assertContains(response, "No response yet")
            self.assertNotContains(response, 'aria-pressed="true"')
            self.assertNotContains(response, f'hx-post="{self.url("leave")}"')
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

    def test_current_card_choice_is_highlighted(self):
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="committed")
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, 'value="committed" aria-pressed="true"')
        self.assertContains(response, 'value="interested" aria-pressed="false"')
        self.assertContains(response, 'aria-pressed="true"', count=1)

    def test_default_activity_offers_only_interested_on_card_and_details(self):
        self.activity.available_responses = []
        self.activity.save()
        for url in [reverse("activities:index"), self.url("detail")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'name="status" value="interested"', count=1)
                for status in ["committed", "question", "more", "vote", "declined"]:
                    self.assertNotContains(response, f'name="status" value="{status}"')
        form = self.client.get(reverse("activities:create")).context["form"]
        self.assertEqual(form["available_responses"].value(), ["interested"])

    def test_later_response_chosen_from_details_remains_visible_on_card(self):
        self.activity.available_responses = ["interested", "committed", "question", "more"]
        self.activity.save()
        for status in ["question", "more"]:
            with self.subTest(status=status):
                detail = self.client.post(
                    self.url("respond"), {"variant": "detail", "status": status},
                    HTTP_HX_REQUEST="true",
                )
                label = ActivityResponseStatus(status).label
                self.assertContains(detail, f"You: {label}")
                card = self.client.get(reverse("activities:index"))
                self.assertContains(card, f">You: {label}</p>")
                self.assertContains(card, f'aria-label="You: {label}"')
                self.assertNotContains(card, 'aria-pressed="true"')
                self.assertContains(card, 'value="interested" aria-pressed="false"')
                self.assertContains(card, 'value="committed" aria-pressed="false"')
                self.assertContains(card, 'aria-label="Remove your response"')

        # A creator removing a choice must not hide the viewer's existing response.
        self.activity.available_responses = ["interested", "committed"]
        self.activity.save()
        self.assertContains(self.client.get(reverse("activities:index")), ">You: Tell me more</p>")

    def filtered_discover_url(self):
        self.activity.cost_type = "free"
        self.activity.location_type = "hybrid"
        self.activity.location_gps = "40,-75"
        self.activity.save()
        return reverse("activities:index") + "?q=walk&online=1&free=1&nearby=1&lat=40&lon=-75&hidden=include&page=1"

    def test_htmx_changes_and_removal_keep_discover_query_in_followup_forms(self):
        destination = self.filtered_discover_url()
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="interested")
        initial = self.client.get(destination)
        leave_form = initial.content.decode().split(f'action="{self.url("leave")}"', 1)[1].split("</form>", 1)[0]
        next_input = f'<input type="hidden" name="next" value="{escape(destination, quote=True)}">'
        self.assertIn(next_input, leave_form)
        changed = self.client.post(
            self.url("respond"), {"status": "question", "variant": "card", "next": destination},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(changed, next_input, count=3, html=True)
        self.assertContains(changed, ">You: I have a question</p>")
        removed = self.client.post(
            self.url("leave"), {"variant": "card", "next": destination}, HTTP_HX_REQUEST="true",
        )
        self.assertContains(removed, next_input, count=2, html=True)
        self.assertNotContains(removed, ">You:")
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer).exists())

    def test_plain_card_changes_and_removal_return_to_filtered_discover(self):
        destination = self.filtered_discover_url()
        for action, status in [("respond", "interested"), ("respond", "question"), ("leave", ""), ("respond", "committed"), ("respond", "committed")]:
            with self.subTest(action=action, status=status):
                response = self.client.post(
                    self.url(action), {"variant": "card", "status": status, "next": destination},
                )
                self.assertRedirects(response, destination)
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer).exists())

    def test_response_return_urls_reject_external_or_unsafe_destinations(self):
        for destination in ["https://example.com/", "//example.com/", "javascript:alert(1)"]:
            for action in ["respond", "leave"]:
                for variant in ["card", "detail"]:
                    with self.subTest(destination=destination, action=action, variant=variant):
                        response = self.client.post(
                            self.url(action), {"variant": variant, "status": "interested", "next": destination},
                        )
                        fallback = self.url("detail") if variant == "detail" else reverse("activities:index")
                        self.assertRedirects(response, fallback)
                        fragment = self.client.post(
                            self.url(action), {"variant": variant, "status": "question", "next": destination},
                            HTTP_HX_REQUEST="true",
                        )
                        self.assertContains(fragment, f'name="next" value="{fallback}"')

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

    def test_question_only_activity_renders_creator_choices_on_card(self):
        self.activity.available_responses = ["question", "declined"]
        self.activity.save()
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, "Details")
        self.assertContains(response, f'hx-post="{self.url("respond")}"')
        self.assertNotContains(response, 'value="interested"')
        self.assertNotContains(response, 'value="committed"')
        detail = self.client.get(self.url("detail"))
        self.assertContains(detail, 'value="question"')
        self.assertContains(detail, 'value="declined"')

    def test_discover_offers_search_and_categories_without_placeholder_controls(self):
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, 'role="search"')
        self.assertContains(response, 'data-discovery-bar')
        self.assertContains(response, '>Search</button>')
        self.assertNotContains(response, 'hx-trigger=')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="category"')
        self.assertNotContains(response, f'href="{reverse("activities:categories")}"')
        for marker in ['name="arrange"', 'name="sort"', "(soon)"]:
            self.assertNotContains(response, marker)
        response = self.client.get(reverse("activities:index"), {"q": "unmatched"})
        self.assertNotContains(response, self.activity.title)

    def test_friends_show_names_and_status_without_column_headers(self):
        from social.models import Friendship, UserProfile

        Friendship.make_pair(self.viewer, self.host)
        UserProfile.objects.update_or_create(user=self.host, defaults={"status_text": "Up for a walk"})
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, "Up for a walk")
        self.assertContains(response, "Who’s around")
        self.assertContains(response, "data-friends-secondary")
        self.assertNotContains(response, "<span>Status</span>")
        self.assertNotContains(response, "<span class=\"font-semibold\">Friends</span>")
