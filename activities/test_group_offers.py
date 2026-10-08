from urllib.parse import quote, urlencode

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .models import Activity, ActivityInvitation, ActivityResponse, GroupJoinOffer


class PostResponseGroupOfferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('offer-host')
        cls.user = create_legacy_user('offer-user')
        cls.other = create_legacy_user('offer-other')
        cls.group = Group.objects.create(owner=cls.host, name='Walking together', access='open')
        cls.activity = Activity.objects.create(host=cls.host, group=cls.group, title='Walk at the park',
                                               starts_at=timezone.now(), cost_type='free',
                                               available_responses=['interested', 'committed', 'question'])
        cls.next = '/?q=park&when=today&when=tomorrow&cost=free&hidden=include&page=2'

    def setUp(self):
        self.client.force_login(self.user)

    def respond(self, status='interested', *, htmx=True, variant='detail', activity=None):
        activity = activity or self.activity
        headers = {'HTTP_HX_REQUEST': 'true'} if htmx else {}
        return self.client.post(reverse('activities:respond', args=[activity.pk]),
            {'status': status, 'variant': variant, 'next': self.next}, **headers)

    def answer(self, action, *, htmx=True, activity=None, next=None):
        activity = activity or self.activity
        headers = {'HTTP_HX_REQUEST': 'true'} if htmx else {}
        return self.client.post(reverse('activities:answer_group_offer', args=[activity.pk]),
            {'action': action, 'next': self.next if next is None else next}, **headers)

    def response_snapshot(self):
        return ActivityResponse.objects.values().get(activity=self.activity, user=self.user)

    def test_offer_only_after_successfully_recorded_response_not_visit_or_invitation(self):
        for page in [reverse('activities:index'), self.activity.get_absolute_url()]:
            self.assertNotContains(self.client.get(page), 'Also join this Group?')
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Also join this Group?')
        self.assertFalse(GroupJoinOffer.objects.exists())
        response = self.respond('question')
        self.assertContains(response, 'Also join this Group?')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertEqual(ActivityResponse.objects.get(user=self.user).status, 'question')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_ordinary_and_invited_responders_can_accept_without_changing_response(self):
        for invited in [False, True]:
            with self.subTest(invited=invited):
                if invited:
                    ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
                self.respond('committed')
                before = self.response_snapshot()
                result = self.answer('join')
                self.assertContains(result, 'You joined the Group.')
                member = GroupMembership.objects.get(group=self.group, user=self.user)
                self.assertEqual((member.status, member.role), ('active', 'member'))
                self.assertEqual(self.response_snapshot(), before)
                self.assertEqual(GroupJoinOffer.objects.get().status, 'accepted')
                self.assertFalse(GroupMembership.objects.filter(user=self.other).exists())
                GroupMembership.objects.filter(user=self.user).delete()
                GroupJoinOffer.objects.all().delete()
                ActivityResponse.objects.all().delete()

    def test_every_supported_response_is_independent_of_optional_join(self):
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        for status in ['interested', 'question', 'committed', 'declined']:
            self.respond(status)
            self.assertEqual(ActivityResponse.objects.get(user=self.user).status, status)
            self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
        self.assertEqual(GroupJoinOffer.objects.count(), 1)

    def test_access_policies_open_closed_unlisted_and_private(self):
        for access, expected in [('open', 'active'), ('closed', 'pending'), ('unlisted', 'active'), ('private', None)]:
            with self.subTest(access=access):
                self.group.access = access; self.group.save(update_fields=['access'])
                page = self.respond('question')
                if expected:
                    self.assertContains(page, self.group.name)
                    if access == 'closed':
                        self.assertContains(page, 'Request to join')
                        self.assertContains(page, 'organizer will review')
                    self.answer('join')
                    self.assertEqual(GroupMembership.objects.get(user=self.user).status, expected)
                else:
                    self.assertNotContains(page, self.group.name)
                    self.assertNotContains(page, 'Also join this Group?')
                    self.assertFalse(GroupJoinOffer.objects.exists())
                    self.assertEqual(self.answer('join').status_code, 404)
                self.assertEqual(ActivityResponse.objects.get(user=self.user).status, 'question')
                GroupMembership.objects.filter(user=self.user).delete()
                GroupJoinOffer.objects.all().delete()
                ActivityResponse.objects.all().delete()

    def test_active_pending_blocked_and_owner_never_offered(self):
        for access in ['open', 'closed', 'unlisted', 'private']:
            self.group.access = access; self.group.save(update_fields=['access'])
            for status in ['active', 'pending', 'blocked']:
                with self.subTest(access=access, status=status):
                    member = GroupMembership.objects.create(group=self.group, user=self.user, status=status)
                    self.assertNotContains(self.respond('question'), 'Also join this Group?')
                    self.assertFalse(GroupJoinOffer.objects.exists())
                    member.refresh_from_db(); self.assertEqual(member.status, status)
                    member.delete(); ActivityResponse.objects.all().delete()
        self.client.force_login(self.host)
        self.assertNotContains(self.respond('question'), 'Also join this Group?')
        self.assertFalse(GroupJoinOffer.objects.exists())

    def test_dismiss_persists_across_sessions_and_other_occurrences(self):
        self.respond('committed')
        before = self.response_snapshot()
        self.assertContains(self.answer('dismiss'), 'response is unchanged')
        self.assertEqual(self.response_snapshot(), before)
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
        self.client.logout(); self.client.force_login(self.user)
        self.assertNotContains(self.respond('question'), 'Also join this Group?')
        other = Activity.objects.create(host=self.host, group=self.group, title='Another walk')
        self.assertNotContains(self.respond(activity=other), 'Also join this Group?')
        self.assertEqual(GroupJoinOffer.objects.get().status, 'dismissed')

    def test_accepted_offer_does_not_repeat_after_leaving_group(self):
        self.respond(); self.answer('join')
        self.client.post(reverse('groups:leave', args=[self.group.pk]))
        self.assertNotContains(self.respond('question'), 'Also join this Group?')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_joining_from_group_details_also_resolves_offer(self):
        self.respond('committed'); before = self.response_snapshot()
        self.client.post(reverse('groups:join', args=[self.group.pk]))
        self.assertEqual(GroupJoinOffer.objects.get().status, 'accepted')
        self.assertEqual(self.response_snapshot(), before)
        self.client.post(reverse('groups:leave', args=[self.group.pk]))
        self.assertNotContains(self.respond('question'), 'Also join this Group?')

    def test_dismissal_survives_source_activity_deletion(self):
        self.respond(); self.answer('dismiss')
        self.activity.delete()
        offer = GroupJoinOffer.objects.get()
        self.assertIsNone(offer.activity_id)
        other = Activity.objects.create(host=self.host, group=self.group, title='Future walk')
        self.assertNotContains(self.respond(activity=other), 'Also join this Group?')

    def test_closed_request_requires_normal_organizer_approval(self):
        self.group.access = 'closed'; self.group.save()
        self.respond('committed'); before = self.response_snapshot()
        self.assertContains(self.answer('join'), 'awaiting organizer approval')
        member = GroupMembership.objects.get(user=self.user)
        self.assertEqual(member.status, 'pending')
        self.client.force_login(self.host)
        self.client.post(reverse('groups:membership_action', args=[self.group.pk, member.pk]), {'action': 'approve'})
        member.refresh_from_db(); self.assertEqual(member.status, 'active')
        self.assertEqual(self.response_snapshot(), before)

    def test_no_offer_for_invalid_full_cancelled_removed_or_groupless_response(self):
        self.assertNotContains(self.respond('invalid'), 'Also join this Group?')
        self.activity.capacity = 0; self.activity.save()
        self.assertNotContains(self.respond('committed'), 'Also join this Group?')
        self.assertFalse(ActivityResponse.objects.exists())
        self.activity.status = 'cancelled'; self.activity.save()
        self.assertNotContains(self.respond(), 'Also join this Group?')
        self.assertFalse(GroupJoinOffer.objects.exists())
        self.activity.status = 'active'; self.activity.group = None; self.activity.save()
        self.assertNotContains(self.respond(), 'Also join this Group?')
        self.assertEqual(ActivityResponse.objects.get(user=self.user).status, 'interested')
        self.assertFalse(GroupJoinOffer.objects.exists())

    def test_toggle_off_and_remove_hide_offer_without_join_or_response_recreation(self):
        self.respond('question')
        self.assertNotContains(self.respond('question'), 'Also join this Group?')
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertEqual(self.answer('join').status_code, 404)
        self.respond('interested')
        result = self.client.post(reverse('activities:leave', args=[self.activity.pk]),
            {'variant': 'detail'}, HTTP_HX_REQUEST='true')
        self.assertNotContains(result, 'Also join this Group?')
        self.assertFalse(ActivityResponse.objects.exists())
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_card_htmx_updates_offer_outside_card_and_retains_discover_context(self):
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        result = self.respond('committed', variant='card')
        self.assertContains(result, 'id="participation-')
        self.assertContains(result, 'id="group-join-offer"')
        self.assertContains(result, 'hx-swap-oob="outerHTML"')
        self.assertContains(result, 'name="next" value="'+self.next.replace('&', '&amp;')+'"')
        self.assertContains(self.client.get(self.next), 'Also join this Group?')
        before = self.response_snapshot()
        result = self.answer('dismiss')
        self.assertNotContains(result, 'participation-')
        self.assertEqual(self.response_snapshot(), before)

    def test_non_js_response_accept_and_dismiss_preserve_repeated_filters(self):
        self.assertRedirects(self.respond(htmx=False), self.next, fetch_redirect_response=False)
        page = self.client.get(self.next)
        self.assertContains(page, 'Also join this Group?')
        self.assertContains(page, 'name="next" value="'+self.next.replace('&', '&amp;')+'"')
        before = self.response_snapshot()
        self.assertRedirects(self.answer('dismiss', htmx=False), self.next, fetch_redirect_response=False)
        self.assertEqual(self.response_snapshot(), before)
        GroupJoinOffer.objects.all().delete()
        self.respond('question', htmx=False)
        before = self.response_snapshot()
        self.assertRedirects(self.answer('join', htmx=False), self.next, fetch_redirect_response=False)
        self.assertEqual(self.response_snapshot(), before)
        self.assertEqual(GroupMembership.objects.get(user=self.user).status, 'active')

    def test_unsafe_next_does_not_redirect_outside_belong(self):
        self.respond()
        self.assertRedirects(self.answer('dismiss', htmx=False, next='https://attacker.example/'),
                             reverse('activities:index'), fetch_redirect_response=False)

    def test_ordinary_details_flow_keeps_filtered_discover_return(self):
        page = self.client.get(self.next)
        self.assertContains(page, '?discover='+quote(self.next, safe='/'))
        detail = self.activity.get_absolute_url()+'?'+urlencode({'discover': self.next})
        page = self.client.get(detail)
        self.assertContains(page, 'href="'+self.next.replace('&', '&amp;')+'"')
        result = self.client.post(reverse('activities:respond', args=[self.activity.pk]),
            {'status': 'question', 'variant': 'detail', 'next': detail})
        self.assertRedirects(result, detail)
        self.assertRedirects(self.answer('dismiss', htmx=False, next=detail), detail)
        self.assertContains(self.client.get(detail), 'href="'+self.next.replace('&', '&amp;')+'"')
        for unsafe in ['https://attacker.example/', '//attacker.example/', '/groups/123/']:
            page = self.client.get(self.activity.get_absolute_url(), {'discover': unsafe})
            self.assertEqual(page.context['discover_path'], reverse('activities:index'))

    def test_recheck_current_group_policy_and_membership_before_acceptance(self):
        for change in ['private', 'blocked', 'pending', 'active']:
            with self.subTest(change=change):
                self.group.access = 'open'; self.group.save()
                GroupJoinOffer.objects.all().delete(); ActivityResponse.objects.all().delete()
                GroupMembership.objects.filter(user=self.user).delete()
                self.respond()
                before = self.response_snapshot()
                if change == 'private':
                    self.group.access = 'private'; self.group.save()
                else:
                    GroupMembership.objects.create(group=self.group, user=self.user, status=change)
                self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Also join this Group?')
                denied = self.answer('join')
                self.assertEqual(denied.status_code, 404)
                self.assertNotContains(denied, self.group.name, status_code=404)
                self.assertEqual(self.response_snapshot(), before)

    def test_policy_change_from_open_to_closed_requests_approval(self):
        self.respond(); self.group.access = 'closed'; self.group.save()
        self.answer('join')
        self.assertEqual(GroupMembership.objects.get(user=self.user).status, 'pending')

    def test_activity_audience_or_group_change_cannot_reuse_offer(self):
        self.respond(); before = self.response_snapshot()
        self.activity.audience = 'friends'; self.activity.save()
        self.assertEqual(self.answer('join').status_code, 404)
        self.assertNotContains(self.client.get(reverse('activities:index')), self.group.name)
        self.activity.audience = 'everyone'
        self.activity.group = Group.objects.create(owner=self.host, name='Different Group', access='open')
        self.activity.save()
        self.assertEqual(self.answer('join').status_code, 404)
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Also join this Group?')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
        self.assertEqual(self.response_snapshot(), before)

    def test_only_own_offer_post_csrf_and_no_arbitrary_group_join(self):
        url = reverse('activities:answer_group_offer', args=[self.activity.pk])
        self.assertEqual(self.answer('join').status_code, 404)
        self.respond()
        self.assertEqual(self.client.get(url).status_code, 405)
        protected = Client(enforce_csrf_checks=True); protected.force_login(self.user)
        self.assertEqual(protected.post(url, {'action': 'join'}).status_code, 403)
        self.assertEqual(self.answer('invalid').status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.answer('join').status_code, 404)
        self.client.logout()
        self.assertEqual(self.answer('join').status_code, 302)
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())

    def test_answer_is_idempotent_and_dismissed_offer_cannot_later_join(self):
        self.respond(); self.answer('dismiss')
        self.answer('join')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
        GroupJoinOffer.objects.all().delete()
        self.respond('question'); self.answer('join'); self.answer('join')
        self.assertEqual(GroupMembership.objects.filter(user=self.user).count(), 1)

    def test_pending_offer_tracks_latest_response_to_same_group_without_multiple_prompts(self):
        self.respond()
        other = Activity.objects.create(host=self.host, group=self.group, title='Later walk')
        self.respond(activity=other)
        self.assertEqual(GroupJoinOffer.objects.get().activity_id, other.pk)
        self.assertEqual(GroupJoinOffer.objects.count(), 1)
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Also join this Group?')
        self.assertContains(self.client.get(other.get_absolute_url()), 'Also join this Group?')

    def test_activity_default_join_path_offers_membership_but_never_joins_automatically(self):
        result = self.client.post(reverse('activities:join', args=[self.activity.pk]),
            {'variant': 'detail'}, HTTP_HX_REQUEST='true')
        self.assertContains(result, 'Also join this Group?')
        self.assertEqual(ActivityResponse.objects.get(user=self.user).status, 'interested')
        self.assertFalse(GroupMembership.objects.filter(user=self.user).exists())
