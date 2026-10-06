from html import escape
from unittest.mock import PropertyMock, patch

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
                if url == self.url("detail"):
                    self.assertContains(response, 'href="https://example.com/walk"')
                else:
                    self.assertNotContains(response, 'href="https://example.com/walk"')
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
                    if variant == "detail":
                        self.assertContains(response, f'hx-post="{self.url("leave")}"')
                    else:
                        self.assertNotContains(response, f'hx-post="{self.url("leave")}"')
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
        self.assertContains(response, "Interested: 1; Count me in: 1")
        self.assertContains(response, 'aria-pressed="true"', count=1)
        response = self.client.post(self.url("respond"), {"variant": "detail", "status": "question"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Interested: 1; Count me in: 0")

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
        self.assertNotContains(response, f'hx-post="{self.url("leave")}"')
        self.assertNotContains(response, '>×</button>')
        self.assertContains(response, 'ui-button--compact ui-response')

    def test_top_two_bands_expose_logistics_people_audience_and_cost(self):
        self.activity.headline = "A marketing headline"
        self.activity.freetext_when = "Saturday morning"
        self.activity.location_name = "River trail"
        self.activity.organizer_name = "Janine"
        self.activity.cost_type = "free"
        self.activity.save()
        html = self.client.get(reverse("activities:index")).content.decode()
        first = html.split('activity-card__band-1', 1)[1].split('activity-card__band-2', 1)[0]
        second = html.split('activity-card__band-2', 1)[1].split('activity-card__band-3', 1)[0]
        self.assertIn(self.activity.title, first)
        self.assertNotIn(self.activity.headline, first)
        self.assertNotIn('activity-card__logistics', first)
        self.assertIn('data-full-text="Saturday morning"', second)
        self.assertIn('data-full-text="River trail"', second)
        self.assertNotIn('class="ui-link', first)
        for value in ["Janine", "Everyone", "Free"]:
            self.assertIn(value, second)
        body = html.split('activity-card__band-4', 1)[1].split('activity-card__band-5', 1)[0]
        footer = html.split('activity-card__band-5', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('>Details', body)
        self.assertNotIn('<a ', footer)
        self.assertNotIn('card-utilities', footer)
        self.assertNotIn('card-current-response', footer)
        self.assertNotIn('Details', footer)
        self.assertNotIn('responses</p>', footer)
        self.assertLessEqual(footer.count('name="status"'), 2)
        self.assertNotIn('truncate', footer)
        self.assertNotIn('>Hide', footer)
        self.assertNotIn('card-utilities', html)
        self.assertNotIn(self.activity.headline, body)
        self.activity.freetext_when = ""
        self.activity.location_name = ""
        self.activity.cost_type = "unknown"
        self.activity.save()
        page = self.client.get(reverse("activities:index"))
        self.assertContains(page, 'data-full-text="Date TBD"')
        self.assertContains(page, 'data-full-text="Location TBD"')
        self.assertContains(page, "Cost TBD")

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
                self.assertNotContains(card, 'aria-label="Remove your response"')
                self.assertContains(self.client.get(self.url('detail')), 'aria-label="Remove your response"')

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
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status="more")
        initial = self.client.get(destination)
        response_form = initial.content.decode().split(f'action="{self.url("respond")}"', 1)[1].split("</form>", 1)[0]
        next_input = f'<input type="hidden" name="next" value="{escape(destination, quote=True)}">'
        self.assertIn(next_input, response_form)
        changed = self.client.post(
            self.url("respond"), {"status": "question", "variant": "card", "next": destination},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(changed, next_input, count=3, html=True)
        self.assertContains(changed, ">You: I have a question</p>")
        removed = self.client.post(
            self.url("leave"), {"variant": "card", "next": destination}, HTTP_HX_REQUEST="true",
        )
        self.assertContains(removed, next_input, count=3, html=True)
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
        self.assertContains(response, f'href="{self.url("detail")}" data-full-text="{self.activity.title}"')
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
        self.assertNotContains(response, 'name="category"')
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

    def test_compact_card_artwork_has_no_controls_or_response_counts(self):
        ActivityResponse.objects.create(user=self.viewer, activity=self.activity, status='question')
        for artwork in [None, '/static/img/test-artwork.png']:
            with self.subTest(artwork=artwork), patch.object(Activity, 'header_image_url', new_callable=PropertyMock, return_value=artwork):
                response = self.client.get(reverse('activities:index'))
                html = response.content.decode()
                image_band = html.split('activity-card__band-3', 1)[1].split('activity-card__band-4', 1)[0]
                self.assertIn('<img' if artwork else 'activity-card__summary', image_band)
                for control in ['<details', '<summary', '<button', '<form', '<a ', 'responses', 'card-utilities']:
                    self.assertNotIn(control, image_band)
                for control in ['card-utilities', '1 response', '>Remove</button>']:
                    # Restrict the assertion to the compact card, excluding page menus.
                    card = html.split('class="activity-card relative', 1)[1].split('data-stack-item', 1)[0].split('</section>', 1)[0]
                    self.assertNotIn(control, card)
                self.assertContains(response, f'href="{self.url("detail")}" data-full-text="{self.activity.title}"')
        details = self.client.get(self.url('detail'))
        self.assertContains(details, '>Hide</button>')
        self.assertContains(details, 'aria-label="Remove your response"')
        self.assertContains(details, '1 response')

    def test_only_actual_committed_responses_receive_confirmation_checks(self):
        for status in ['interested', 'committed', 'more', 'question', 'vote', 'declined']:
            self.activity.available_responses = ['committed', status] if status != 'committed' else ['committed', 'interested']
            self.activity.save()
            for variant in ['card', 'detail']:
                with self.subTest(status=status, variant=variant):
                    ActivityResponse.objects.filter(user=self.viewer, activity=self.activity).delete()
                    untouched = self.client.get(self.url('detail') if variant == 'detail' else reverse('activities:index'))
                    self.assertNotContains(untouched, 'ui-response--confirmed')
                    selected = self.client.post(self.url('respond'), {'status': status, 'variant': variant}, HTTP_HX_REQUEST='true')
                    self.assertContains(selected, 'aria-pressed="true"', count=1)
                    if status == 'committed':
                        self.assertContains(selected, 'ui-response--confirmed', count=1)
                    else:
                        self.assertNotContains(selected, 'ui-response--confirmed')
                    cleared = self.client.post(self.url('respond'), {'status': status, 'variant': variant}, HTTP_HX_REQUEST='true')
                    self.assertNotContains(cleared, 'ui-response--confirmed')
                    self.assertNotContains(cleared, 'aria-pressed="true"')

    def test_external_cta_does_not_receive_response_confirmation(self):
        response = self.client.get(self.url('detail'))
        self.assertContains(response, 'href="https://example.com/walk"')
        self.assertNotContains(response, 'ui-response--confirmed')
