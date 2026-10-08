"""Normal Group admission, shared by Group Details and optional Activity offers."""
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Group, GroupAccess, GroupMembership, MemberStatus


def join_group(pk, user):
    with transaction.atomic():
        group = get_object_or_404(Group.objects.select_for_update(), pk=pk)
        if (not group.can_view(user) or group.access == GroupAccess.PRIVATE
                or group.memberships.filter(user=user, status=MemberStatus.BLOCKED).exists()):
            raise Http404
        membership, _ = GroupMembership.objects.get_or_create(group=group, user=user, defaults={
            'status': MemberStatus.PENDING if group.access == GroupAccess.CLOSED else MemberStatus.ACTIVE,
        })
        # Explicit normal join also completes legacy pending Open/Unlisted requests.
        if membership.status == MemberStatus.PENDING and group.access in [GroupAccess.OPEN, GroupAccess.UNLISTED]:
            membership.status = MemberStatus.ACTIVE
            membership.save(update_fields=['status'])
        group.activity_join_offers.filter(user=user, status='pending').update(status='accepted')
        return membership
