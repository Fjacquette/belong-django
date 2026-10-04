from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import GroupForm
from .models import Group, GroupMembership, JoinPolicy, MemberRole, MemberStatus


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
        "can_join": not membership and group.join_policy != JoinPolicy.INVITE,
    })


@login_required
@require_POST
def join(request, pk):
    with transaction.atomic():
        group = _visible_group(request.user, pk)
        # Serialize membership creation/policy decisions with organizer actions.
        group = Group.objects.select_for_update().get(pk=group.pk)
        if group.join_policy == JoinPolicy.INVITE:
            raise Http404
        GroupMembership.objects.get_or_create(group=group, user=request.user, defaults={
            "status": MemberStatus.ACTIVE if group.join_policy == JoinPolicy.OPEN else MemberStatus.PENDING,
        })
    return redirect(group)


@login_required
@require_POST
def leave(request, pk):
    with transaction.atomic():
        group = get_object_or_404(Group.objects.select_for_update(), pk=pk)
        if group.owner_id == request.user.pk:
            raise Http404
        member = get_object_or_404(GroupMembership, group=group, user=request.user)
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
        if action == "decline" and member.status == MemberStatus.PENDING:
            member.delete()
            return redirect(group)
        elif action == "approve" and member.status == MemberStatus.PENDING:
            member.status = MemberStatus.ACTIVE
        elif action in ["promote", "demote"] and group.owner_id == request.user.pk and member.user_id != group.owner_id and member.status == MemberStatus.ACTIVE:
            member.role = MemberRole.ORGANIZER if action == "promote" else MemberRole.MEMBER
        else:
            raise Http404
        member.full_clean()
        member.save(update_fields=["status", "role"])
    messages.success(request, "Membership updated.")
    return redirect(group)
