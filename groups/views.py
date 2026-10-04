from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import GroupForm
from .models import Group, GroupAccess, GroupMembership, MemberRole, MemberStatus


def _visible_group(user, pk):
    group = get_object_or_404(Group.objects.select_related("owner"), pk=pk)
    if not group.can_view(user):
        raise Http404
    return group


@login_required
def create(request):
    form = GroupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
            GroupMembership.objects.create(group=group, user=request.user, role=MemberRole.ORGANIZER)
        return redirect(group)
    return render(request, "groups/form.html", {"form": form})


@login_required
def detail(request, pk):
    group = _visible_group(request.user, pk)
    membership = group.membership_for(request.user)
    organizer = group.can_organize(request.user)
    active = membership and membership.status == MemberStatus.ACTIVE
    members = group.memberships.filter(status=MemberStatus.ACTIVE).select_related("user")
    return render(request, "groups/detail.html", {
        "group": group, "membership": membership, "organizer": organizer,
        "is_owner": group.owner_id == request.user.pk,
        "members": members if active or organizer else None,
        "member_count": members.count(),
        "pending": group.memberships.filter(status=MemberStatus.PENDING).select_related("user") if organizer else None,
        "blocked": group.memberships.filter(status=MemberStatus.BLOCKED).select_related("user") if organizer else None,
        "can_join": group.access != GroupAccess.PRIVATE and (
            not membership or membership.status == MemberStatus.PENDING and group.access in [GroupAccess.OPEN, GroupAccess.UNLISTED]
        ),
    })


@login_required
@require_POST
def join(request, pk):
    with transaction.atomic():
        group = _visible_group(request.user, pk)
        # Serialize membership creation/policy decisions with organizer actions.
        group = Group.objects.select_for_update().get(pk=group.pk)
        if group.access == GroupAccess.PRIVATE or group.memberships.filter(user=request.user, status=MemberStatus.BLOCKED).exists():
            raise Http404
        membership, _ = GroupMembership.objects.get_or_create(group=group, user=request.user, defaults={
            "status": MemberStatus.PENDING if group.access == GroupAccess.CLOSED else MemberStatus.ACTIVE,
        })
        # Existing pending requests survive migration. Joining an Open/Unlisted
        # group explicitly now completes membership without organizer approval.
        if membership.status == MemberStatus.PENDING and group.access in [GroupAccess.OPEN, GroupAccess.UNLISTED]:
            membership.status = MemberStatus.ACTIVE
            membership.save(update_fields=["status"])
    return redirect(group)


@login_required
@require_POST
def leave(request, pk):
    with transaction.atomic():
        group = get_object_or_404(Group.objects.select_for_update(), pk=pk)
        if group.owner_id == request.user.pk:
            raise Http404
        member = get_object_or_404(GroupMembership, group=group, user=request.user)
        if member.status == MemberStatus.BLOCKED:
            raise Http404
        member.delete()
    return redirect("activities:index")


@login_required
@require_POST
def membership_action(request, pk, member_pk):
    with transaction.atomic():
        group = get_object_or_404(Group.objects.select_for_update(), pk=pk)
        if not group.can_organize(request.user):
            raise Http404
        member = get_object_or_404(GroupMembership, pk=member_pk, group=group)
        action = request.POST.get("action")
        if action == "unblock" and member.status == MemberStatus.BLOCKED:
            member.delete()
            return redirect(group)
        elif action == "block" and member.user_id != group.owner_id and (member.role != MemberRole.ORGANIZER or group.owner_id == request.user.pk):
            member.status = MemberStatus.BLOCKED
            member.role = MemberRole.MEMBER
        elif action == "decline" and member.status == MemberStatus.PENDING:
            member.delete()
            return redirect(group)
        elif action == "approve" and member.status == MemberStatus.PENDING and group.access != GroupAccess.PRIVATE:
            member.status = MemberStatus.ACTIVE
        elif action in ["promote", "demote"] and group.owner_id == request.user.pk and member.user_id != group.owner_id and member.status == MemberStatus.ACTIVE:
            member.role = MemberRole.ORGANIZER if action == "promote" else MemberRole.MEMBER
        else:
            raise Http404
        member.full_clean()
        member.save(update_fields=["status", "role"])
    messages.success(request, "Membership updated.")
    return redirect(group)
