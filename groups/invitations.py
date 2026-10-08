"""Email-bound invitations; the database stores only token digests."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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
    from belong.email_controls import lock_controls, owned_url, dispatch, invitation_reservation, invitation_error
    from social.models import OutboundEmailAttempt
    email = email.strip().lower()
    from django.core.validators import validate_email
    validate_email(email)
    with transaction.atomic():
        lock_controls()
        group = Group.objects.select_for_update().get(pk=group.pk)
        now = timezone.now()
        attempt, reason = invitation_reservation(request, inviter, email, group=group)
        if not reason:
            members = group.memberships.filter(user__email__iexact=email)
            if members.filter(status=MemberStatus.BLOCKED).exists():
                reason = 'blocked_member'
            elif members.filter(status=MemberStatus.ACTIVE).exists():
                attempt.outcome = 'not_needed'
                attempt.save(update_fields=['outcome'])
                return False
        if reason:
            attempt.outcome, attempt.reason = 'blocked', reason
            attempt.save(update_fields=['outcome', 'reason'])
        else:
            token = secrets.token_urlsafe(32)
            invitation, _ = GroupInvitation.objects.update_or_create(group=group, email=email, defaults={
                'inviter': inviter, 'token_digest': digest(token), 'status': 'pending',
                'expires_at': now+timedelta(days=7), 'accepted_by': None, 'accepted_at': None,
            })
    # Raise only after commit, preserving denied attempts in the diagnostic trail.
    if reason:
        raise invitation_error(reason)
    try:
        url = owned_url('groups:invitation', token)
    except Exception:
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='failed', reason='origin_configuration')
        raise ValidationError('Invitation email could not be sent. Please retry later.')
    # Never interpolate organizer/group text: it can contain arbitrary links or content.
    if not dispatch(attempt, 'Your Belong group invitation',
            f'You have been invited to a group on Belong.\n\nReview and accept: {url}\n\nThis invitation expires in seven days. Use this email address to sign in or create an account.', email):
        raise ValidationError('Invitation email could not be sent. Please retry later.')
    return True


def pending_invitation(request):
    reference = request.session.get('pending_group_invitation')
    if not isinstance(reference, int) or isinstance(reference, bool):
        return None
    return GroupInvitation.objects.select_related('group', 'inviter__profile').filter(pk=reference).first()


def accept_invitation(token, user):
    invitation = find_invitation(token)
    return accept_reference(invitation.pk if invitation else None, user)


def accept_reference(reference, user):
    # Internal only: reference must come from a previously validated bearer link/session.
    with transaction.atomic():
        invitation = GroupInvitation.objects.filter(pk=reference).first()
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
            try:
                with transaction.atomic():
                    user.save(update_fields=['email'])
            except IntegrityError as error:
                raise ValidationError('Another account already uses the invited email address. Sign in with that account.') from error
        # The invited bearer token proves control only of this exact address.
        profile = user.profile
        if not profile.can_use_belong:
            raise ValidationError('Verify your email before accepting this invitation.')
        if not profile.email_verified_at:
            profile.email_verified_at = timezone.now()
            profile.legacy_access = False
            profile.save(update_fields=['email_verified_at', 'legacy_access'])
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
    invitation = pending_invitation(request)
    if not invitation:
        request.session.pop('pending_group_invitation', None)
        return None
    from django.contrib import messages
    try:
        group = accept_reference(invitation.pk, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return reverse('groups:pending_invitation')
    request.session.pop('pending_group_invitation', None)
    messages.success(request, 'Invitation accepted.' if group else 'This invitation was already used.')
    return group.get_absolute_url() if group else reverse('activities:index')
