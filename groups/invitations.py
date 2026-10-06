"""Email-bound invitations; the database stores only token digests."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Group, GroupInvitation, GroupMembership, MemberStatus


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def find_invitation(token):
    return GroupInvitation.objects.select_related('group', 'inviter').filter(token_digest=digest(token)).first()


def usable(invitation):
    return invitation and invitation.status == 'pending' and invitation.expires_at > timezone.now()


def email_claimed(email, user):
    return get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists()


def issue_invitation(group, inviter, email, request):
    with transaction.atomic():
        group = Group.objects.select_for_update().get(pk=group.pk)
        if not group.can_organize(inviter):
            raise ValidationError('Only current organizers may invite people.')
        email = email.strip().lower()
        members = group.memberships.filter(user__email__iexact=email)
        if members.filter(status=MemberStatus.BLOCKED).exists():
            raise ValidationError('This address belongs to a blocked member. Unblock membership first.')
        if members.filter(status=MemberStatus.ACTIVE).exists():
            return False
        token = secrets.token_urlsafe(32)
        invitation, _ = GroupInvitation.objects.update_or_create(group=group, email=email, defaults={
            'inviter': inviter, 'token_digest': digest(token), 'status': 'pending',
            'expires_at': timezone.now() + timedelta(days=7), 'accepted_by': None,
            'accepted_at': None,
        })
        url = request.build_absolute_uri(reverse('groups:invitation', args=[token]))
        delivered = send_mail(f'Invitation to {group.name}',
                  f'{inviter.get_full_name() or inviter.username} invited you to {group.name}.\n\n'
                  f'Accept your invitation: {url}\n\nThis invitation expires in 7 days. '
                  'Sign in or create an account using the invited email address.',
                  None, [email], fail_silently=False)
        if delivered != 1:
            raise RuntimeError('Invitation email was not delivered.')
        return True


def accept_invitation(token, user):
    with transaction.atomic():
        invitation = find_invitation(token)
        if not invitation:
            raise ValidationError('This invitation is unavailable.')
        group = Group.objects.select_for_update().get(pk=invitation.group_id)
        invitation = GroupInvitation.objects.select_for_update().get(pk=invitation.pk)
        # Re-read under a lock so a stale request cannot overwrite a newly bound email.
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        current_email = user.email.strip().lower()
        if current_email and current_email != invitation.email:
            raise ValidationError('Sign in with the account that uses the invited email address.')
        member = group.memberships.filter(user=user).first()
        if member and member.status == MemberStatus.BLOCKED:
            raise ValidationError('This membership is blocked. Contact the organizer.')
        if invitation.status == 'accepted' and invitation.accepted_by_id == user.pk and current_email == invitation.email:
            # A consumed invitation must not recreate membership after leaving.
            return group if member and member.status == MemberStatus.ACTIVE else None
        if not usable(invitation):
            raise ValidationError('This invitation has expired or is no longer available.')
        if not current_email:
            if email_claimed(invitation.email, user):
                raise ValidationError('Another account already uses the invited email address. Sign in with that account.')
            user.email = invitation.email
            user.save(update_fields=['email'])
        member, _ = GroupMembership.objects.get_or_create(group=group, user=user)
        if member.status == MemberStatus.PENDING:
            member.status = MemberStatus.ACTIVE
            member.save(update_fields=['status'])
        invitation.status = 'accepted'
        invitation.accepted_by = user
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['status', 'accepted_by', 'accepted_at'])
        return group


def finish_pending(request):
    token = request.session.get('group_invitation')
    if not token:
        return None
    from django.contrib import messages
    try:
        group = accept_invitation(token, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return reverse('groups:invitation', args=[token])
    request.session.pop('group_invitation', None)
    messages.success(request, 'Invitation accepted.' if group else 'This invitation was already used.')
    return group.get_absolute_url() if group else reverse('activities:index')
