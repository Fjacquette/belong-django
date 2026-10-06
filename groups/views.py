from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import GroupForm, InvitationForm
from .models import Group, GroupAccess, GroupMembership, MemberRole, MemberStatus


def _visible_group(user, pk):
    group = get_object_or_404(Group.objects.select_related("owner"), pk=pk)
    if not group.can_view(user):
        raise Http404
    return group


@login_required
def create(request):
    form = GroupForm(request.POST if request.method == "POST" else None, request.FILES if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
            GroupMembership.objects.create(group=group, user=request.user, role=MemberRole.ORGANIZER)
        return redirect(group)
    return render(request, "groups/form.html", {"form": form, "suppress_create": True})


@login_required
def edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if not group.can_organize(request.user):
        raise Http404
    form = GroupForm(request.POST if request.method == 'POST' else None,
                     request.FILES if request.method == 'POST' else None, instance=group, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        return redirect(group)
    return render(request, 'groups/form.html', {'form': form, 'group': group, 'suppress_create': True})


@login_required
def detail(request, pk, invitation_form=None):
    group = _visible_group(request.user, pk)
    membership = group.membership_for(request.user)
    organizer = group.can_organize(request.user)
    active = membership and membership.status == MemberStatus.ACTIVE
    members = group.memberships.filter(status=MemberStatus.ACTIVE).select_related("user")
    return render(request, "groups/detail.html", {
        "group": group, "membership": membership, "organizer": organizer,
        "invitation_form": (invitation_form if invitation_form is not None else InvitationForm()) if organizer else None,
        "invitations": group.invitations.all() if organizer else None,
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


@login_required
@require_POST
def invite(request, pk):
    from django.core.exceptions import ValidationError
    from .invitations import issue_invitation
    group = get_object_or_404(Group, pk=pk)
    if not group.can_organize(request.user):
        raise Http404
    form = InvitationForm(request.POST)
    results = []
    if form.is_valid():
        for email in form.cleaned_data['emails']:
            try:
                sent = issue_invitation(group, request.user, email, request)
                results.append(f'{email}: invitation sent.' if sent else f'{email}: already a member.')
            except ValidationError as error:
                results.append(f'{email}: {error.messages[0]}')
            except (OSError, SMTPException, RuntimeError):
                # Delivery failure rolls back token rotation; retry remains possible.
                import logging
                logging.getLogger(__name__).exception('Group invitation delivery failed for group %s', group.pk)
                results.append(f'{email}: email could not be sent. Please retry.')
    else:
        return detail(request, pk, invitation_form=form)
    for result in results:
        messages.info(request, result)
    return redirect(group)


@login_required
@require_POST
def revoke_invitation(request, pk, invitation_pk):
    from .models import GroupInvitation
    with transaction.atomic():
        group = get_object_or_404(Group.objects.select_for_update(), pk=pk)
        if not group.can_organize(request.user):
            raise Http404
        invitation = get_object_or_404(GroupInvitation, pk=invitation_pk, group=group)
        if invitation.status == 'pending':
            invitation.status = 'revoked'
            invitation.save(update_fields=['status', 'updated_at'])
    return redirect(group)


def invitation(request, token):
    from django.core.exceptions import ValidationError
    from .invitations import find_invitation, usable, accept_invitation, email_claimed
    invitation = find_invitation(token)
    available = usable(invitation)
    matched = request.user.is_authenticated and invitation and request.user.email.strip().lower() == invitation.email
    bind_email = available and request.user.is_authenticated and not request.user.email.strip() and not email_claimed(invitation.email, request.user)
    # A valid bearer link also permits an email-less account to explicitly accept.
    show_context = available and (not request.user.is_authenticated or matched or bind_email)
    if request.method == 'POST':
        if request.POST.get('auth') == 'switch' and available:
            from django.contrib.auth import logout
            logout(request)
            request.session['group_invitation'] = token
            return redirect('login')
        if not request.user.is_authenticated:
            if not available:
                raise Http404
            request.session['group_invitation'] = token
            return redirect('signup' if request.POST.get('auth') == 'signup' else 'login')
        try:
            group = accept_invitation(token, request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            request.session.pop('group_invitation', None)
            return redirect(group or 'activities:index')
    response = render(request, 'groups/invitation.html', {'invitation': invitation if show_context else None,
                                                       'available': available, 'matched': matched, 'bind_email': bind_email})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'same-origin'
    return response
