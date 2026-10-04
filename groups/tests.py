from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from activities.forms import ActivityForm
from activities.models import Activity, ActivityResponse
from .forms import GroupForm
from .models import Group, GroupMembership, GroupAccess, MemberRole, MemberStatus


class GroupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="janine")
        cls.member = User.objects.create_user(username="hiker")
        cls.outsider = User.objects.create_user(username="visitor")
        cls.group = Group.objects.create(name="Hikes with Janine", owner=cls.owner, access=GroupAccess.OPEN)
        cls.owner_membership = GroupMembership.objects.create(group=cls.group, user=cls.owner, role=MemberRole.ORGANIZER)
        cls.membership = GroupMembership.objects.create(group=cls.group, user=cls.member)

    def action(self, user, member, action):
        self.client.force_login(user)
        return self.client.post(reverse("groups:membership_action", args=[self.group.pk, member.pk]), {"action": action})

    def test_creation_sets_owner_and_active_organizer_atomically(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("groups:create"), {"name": "Evening walks", "description": "Walk together", "access": "unlisted", "owner": self.owner.pk})
        group = Group.objects.get(name="Evening walks")
        self.assertRedirects(response, group.get_absolute_url())
        self.assertEqual(group.owner, self.outsider)
        membership = group.memberships.get(user=self.outsider)
        self.assertEqual((membership.role, membership.status), ("organizer", "active"))
        self.assertEqual(Activity.objects.count(), 0)

    def test_invalid_creation_does_not_create_group_or_membership(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("groups:create"), {"name": "", "access": "unknown"})
        self.assertContains(response, "This field is required")
        self.assertEqual(Group.objects.count(), 1)

    def test_detail_requires_login(self):
        response = self.client.get(self.group.get_absolute_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_private_group_only_owner_and_active_members_can_view(self):
        self.group.access = GroupAccess.PRIVATE
        self.group.save()
        GroupMembership.objects.create(group=self.group, user=self.outsider, status=MemberStatus.PENDING)
        for user, status in [(self.owner, 200), (self.member, 200), (self.outsider, 404)]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.group.get_absolute_url()).status_code, status)

    def test_public_and_unlisted_identity_visible_but_roster_is_members_only(self):
        for access in [GroupAccess.OPEN, GroupAccess.CLOSED, GroupAccess.UNLISTED]:
            self.group.access = access
            self.group.save()
            self.client.force_login(self.outsider)
            response = self.client.get(self.group.get_absolute_url())
            self.assertContains(response, self.group.name)
            self.assertNotContains(response, self.member.username)
            self.client.force_login(self.member)
            self.assertContains(self.client.get(self.group.get_absolute_url()), self.member.username)

    def test_open_join_is_idempotent_and_cannot_promote_self(self):
        self.client.force_login(self.outsider)
        url = reverse("groups:join", args=[self.group.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"role": "organizer", "status": "active"}).status_code, 302)
        membership = self.group.memberships.get(user=self.outsider)
        self.assertEqual((membership.role, membership.status), ("member", "active"))

    def test_approval_join_and_organizer_approval(self):
        self.group.access = GroupAccess.CLOSED
        self.group.save()
        self.client.force_login(self.outsider)
        self.client.post(reverse("groups:join", args=[self.group.pk]))
        pending = self.group.memberships.get(user=self.outsider)
        self.assertEqual(pending.status, "pending")
        self.assertFalse(self.group.can_organize(self.outsider))
        self.assertContains(self.client.get(self.group.get_absolute_url()), "awaiting organizer approval")
        self.assertEqual(self.action(self.member, pending, "approve").status_code, 404)
        self.assertEqual(self.action(self.owner, pending, "approve").status_code, 302)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "active")

    def test_invite_only_cannot_self_join(self):
        self.group.access = GroupAccess.PRIVATE
        self.group.save()
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(reverse("groups:join", args=[self.group.pk])).status_code, 404)
        self.assertFalse(self.group.memberships.filter(user=self.outsider).exists())

    def test_private_legacy_pending_request_cannot_bypass_invitation(self):
        self.group.access = GroupAccess.PRIVATE
        self.group.save()
        pending = GroupMembership.objects.create(group=self.group, user=self.outsider, status="pending")
        self.assertEqual(self.action(self.owner, pending, "approve").status_code, 404)
        self.assertNotContains(self.client.get(self.group.get_absolute_url()), 'value="approve"')
        pending.refresh_from_db()
        self.assertEqual(pending.status, "pending")
        self.assertFalse(self.group.can_view(self.outsider))

    def test_owner_can_add_and_remove_additional_organizer(self):
        self.assertEqual(self.action(self.owner, self.membership, "promote").status_code, 302)
        self.assertTrue(self.group.can_organize(self.member))
        pending = GroupMembership.objects.create(group=self.group, user=self.outsider, status="pending")
        self.assertEqual(self.action(self.member, pending, "approve").status_code, 302)
        self.assertEqual(self.action(self.member, self.owner_membership, "demote").status_code, 404)
        self.assertEqual(self.action(self.owner, self.membership, "demote").status_code, 302)
        self.assertFalse(self.group.can_organize(self.member))

    def test_cannot_modify_membership_of_another_group(self):
        other = Group.objects.create(name="Other", owner=self.outsider)
        other_member = GroupMembership.objects.create(group=other, user=self.member)
        self.assertEqual(self.action(self.owner, other_member, "promote").status_code, 404)

    def test_member_can_leave_but_owner_cannot(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("groups:leave", args=[self.group.pk])).status_code, 302)
        self.assertFalse(self.group.memberships.filter(user=self.member).exists())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse("groups:leave", args=[self.group.pk])).status_code, 404)
        self.assertTrue(self.group.memberships.filter(user=self.owner).exists())

    def test_pending_request_can_be_cancelled_or_declined(self):
        pending = GroupMembership.objects.create(group=self.group, user=self.outsider, status="pending")
        self.assertEqual(self.action(self.owner, pending, "decline").status_code, 302)
        self.assertFalse(GroupMembership.objects.filter(pk=pending.pk).exists())
        GroupMembership.objects.create(group=self.group, user=self.outsider, status="pending")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(reverse("groups:leave", args=[self.group.pk])).status_code, 302)

    def test_mutations_require_post_and_csrf(self):
        self.client.force_login(self.owner)
        for url in [reverse("groups:join", args=[self.group.pk]), reverse("groups:leave", args=[self.group.pk]), reverse("groups:membership_action", args=[self.group.pk, self.membership.pk])]:
            self.assertEqual(self.client.get(url).status_code, 405)
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("groups:join", args=[self.group.pk])).status_code, 403)

    def test_membership_integrity_constraints(self):
        for values in [dict(user=self.member), dict(user=self.outsider, role="invalid"), dict(user=self.outsider, status="invalid"), dict(user=self.outsider, role="organizer", status="pending")]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                GroupMembership.objects.create(group=self.group, **values)
        self.owner_membership.role = "member"
        with self.assertRaises(ValidationError):
            self.owner_membership.full_clean()

    def test_group_enum_constraints(self):
        for values in [dict(access="invalid")]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Group.objects.create(name="Invalid", owner=self.owner, **values)

    def test_four_modes_are_the_only_creation_and_admin_choices(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("groups:create"))
        form = page.context["form"]
        self.assertEqual(list(form.fields), ["name", "description", "access"])
        self.assertEqual([value for value, label in form.fields["access"].choices if value], GroupAccess.values)
        from django.test import RequestFactory
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        admin_form = admin.site._registry[Group].get_form(request)
        self.assertIn("access", admin_form.base_fields)
        self.assertNotIn("join_policy", admin_form.base_fields)
        self.assertNotIn("visibility", admin_form.base_fields)
        for access in GroupAccess.values:
            response = self.client.post(reverse("groups:create"), {"name": f"Mode {access}", "access": access, "visibility": "private", "join_policy": "open"})
            group = Group.objects.get(name=f"Mode {access}")
            self.assertRedirects(response, group.get_absolute_url())
            self.assertEqual(group.access, access)
        invalid = GroupForm({"name": "Bad", "access": "public"})
        self.assertFalse(invalid.is_valid())
        invalid_group = Group(name="Bad", owner=self.owner, access="public")
        with self.assertRaises(ValidationError):
            invalid_group.full_clean()

    def test_unlisted_joins_immediately_through_link_without_approval(self):
        self.group.access = GroupAccess.UNLISTED
        self.group.save()
        self.client.force_login(self.outsider)
        page = self.client.get(self.group.get_absolute_url())
        self.assertContains(page, "Join group")
        self.assertNotContains(page, "Request to join")
        self.client.post(reverse("groups:join", args=[self.group.pk]))
        self.assertEqual(self.group.memberships.get(user=self.outsider).status, "active")
        # Discover continues to surface activities, never a proactive group list.
        self.assertNotContains(self.client.get(reverse("activities:index")), self.group.name)

    def test_pending_request_can_complete_self_join_in_open_and_unlisted_modes(self):
        membership = GroupMembership.objects.create(group=self.group, user=self.outsider, status="pending")
        self.client.force_login(self.outsider)
        for access in [GroupAccess.OPEN, GroupAccess.UNLISTED]:
            self.group.access = access
            self.group.save()
            membership.status = "pending"
            membership.save()
            page = self.client.get(self.group.get_absolute_url())
            self.assertContains(page, "Join group")
            self.assertNotContains(page, "awaiting organizer approval")
            self.client.post(reverse("groups:join", args=[self.group.pk]))
            membership.refresh_from_db()
            self.assertEqual(membership.status, "active")

    def test_block_prevents_join_and_leave_bypass_until_organizer_unblocks(self):
        for access in [GroupAccess.OPEN, GroupAccess.CLOSED, GroupAccess.UNLISTED]:
            self.group.access = access
            self.group.save()
            self.assertEqual(self.action(self.owner, self.membership, "block").status_code, 302)
            self.client.force_login(self.member)
            self.assertContains(self.client.get(self.group.get_absolute_url()), "blocked from joining")
            for route in ["join", "leave"]:
                self.assertEqual(self.client.post(reverse(f"groups:{route}", args=[self.group.pk])).status_code, 404)
            self.assertEqual(self.action(self.member, self.membership, "unblock").status_code, 404)
            self.assertEqual(self.action(self.owner, self.membership, "unblock").status_code, 302)
            self.client.force_login(self.member)
            self.client.post(reverse("groups:join", args=[self.group.pk]))
            self.membership = self.group.memberships.get(user=self.member)
            self.assertEqual(self.membership.status, "pending" if access == GroupAccess.CLOSED else "active")

    def test_moderator_cannot_block_owner_or_peer_organizer(self):
        self.assertEqual(self.action(self.owner, self.membership, "promote").status_code, 302)
        self.assertEqual(self.action(self.member, self.owner_membership, "block").status_code, 404)
        self.assertEqual(self.action(self.member, self.membership, "block").status_code, 404)
        other = GroupMembership.objects.create(group=self.group, user=self.outsider)
        self.assertEqual(self.action(self.member, other, "block").status_code, 302)
        self.assertEqual(self.action(self.member, other, "unblock").status_code, 302)
        self.assertEqual(self.action(self.owner, self.membership, "block").status_code, 302)
        self.assertFalse(self.group.can_organize(self.member))

    def test_blocked_membership_does_not_gate_activity_response(self):
        self.action(self.owner, self.membership, "block")
        activity = Activity.objects.create(title="Public hike", description="Walk", host=self.owner, group=self.group)
        self.client.force_login(self.member)
        self.client.post(reverse("activities:respond", args=[activity.pk]), {"status": "interested"})
        self.assertTrue(ActivityResponse.objects.filter(activity=activity, user=self.member).exists())

    def test_activity_group_optional_and_participation_not_gated(self):
        ordinary = Activity.objects.create(title="Walk", description="Together", host=self.owner)
        linked = Activity.objects.create(title="Group walk", description="Together", host=self.owner, group=self.group)
        self.assertIsNone(ordinary.group_id)
        self.client.force_login(self.outsider)
        for activity in [ordinary, linked]:
            self.assertEqual(self.client.get(reverse("activities:detail", args=[activity.pk])).status_code, 200)
            self.client.post(reverse("activities:respond", args=[activity.pk]), {"status": "interested"})
            self.assertTrue(ActivityResponse.objects.filter(activity=activity, user=self.outsider).exists())
        self.assertFalse(self.group.memberships.filter(user=self.outsider).exists())

    def test_private_group_not_disclosed_by_public_activity(self):
        self.group.access = "private"
        self.group.save()
        activity = Activity.objects.create(title="Public walk", description="Walk", host=self.owner, group=self.group)
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("activities:detail", args=[activity.pk])), self.group.name)

    def test_activity_form_only_allows_groups_user_organizes(self):
        for user, expected in [(self.owner, [self.group]), (self.member, []), (self.outsider, [])]:
            form = ActivityForm(user=user)
            self.assertEqual(list(form.fields["group"].queryset), expected)
        self.membership.role = "organizer"
        self.membership.save()
        self.assertEqual(list(ActivityForm(user=self.member).fields["group"].queryset), [self.group])
        form = ActivityForm({"title": "Forged", "description": "Test", "group": self.group.pk}, user=self.outsider)
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)

    def test_activity_creation_prefills_group_and_saves_optional_link(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("activities:create"), {"group": self.group.pk})
        self.assertEqual(response.context["form"].initial["group"], str(self.group.pk))
        data = {"title": "Saturday hike", "description": "Trail walk", "location_type": "tbd", "audience": "everyone", "cost_type": "unknown"}
        for group_id in [self.group.pk, ""]:
            response = self.client.post(reverse("activities:create"), {**data, "group": group_id})
            self.assertEqual(response.status_code, 302)
            activity = Activity.objects.latest("pk")
            self.assertEqual(activity.group_id, group_id or None)

    def test_empty_post_creation_shows_required_errors(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.post(reverse("groups:create"), {}), "This field is required")

    def test_group_deletion_preserves_linked_activity(self):
        activity = Activity.objects.create(title="Keep me", description="Walk", host=self.owner, group=self.group)
        self.group.delete()
        activity.refresh_from_db()
        self.assertIsNone(activity.group_id)

    def test_admin_and_create_chooser_available_without_group_navigation(self):
        self.assertIn(Group, admin.site._registry)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("activities:index"))
        self.assertContains(response, 'aria-label="Create"')
        self.assertContains(response, reverse("groups:create"))
        header = response.content.decode().split("</header>")[0]
        self.assertNotIn("Groups", header)
