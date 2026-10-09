"""Email-bound, single-use beta admission. Caller serializes with the mail-control lock."""
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from social.models import BetaAdmission
from .email_controls import lock_controls

ERROR = 'A valid beta invitation is required for this email address. Check your code or request a new invitation.'


def verifier(value):
    return salted_hmac('belong.beta-admission.v1', value, algorithm='sha256').hexdigest()


def issue_code(email, issuer):
    if not issuer.is_active or not issuer.is_superuser:
        raise PermissionDenied
    email = email.strip().lower()
    validate_email(email)
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        lock_controls()
        admission = BetaAdmission.objects.create(email=email, verifier=verifier('code:'+token),
            issued_by=issuer, expires_at=timezone.now()+timedelta(days=7))
    return admission, token


def revoke(admissions, actor):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    with transaction.atomic():
        lock_controls()
        return admissions.filter(revoked_at__isnull=True, redeemed_at__isnull=True).update(revoked_at=timezone.now(), revoked_by=actor)


def valid(admission, email):
    if (not admission or admission.email != email or admission.revoked_at or admission.redeemed_at
            or admission.expires_at <= timezone.now()):
        return False
    if admission.kind == 'code':
        return True
    invitation = admission.group_invitation if admission.kind == 'group' else admission.activity_invitation
    return valid_invitation(invitation, email, admission.kind, admission.source_digest)


def valid_invitation(invitation, email, kind, source_digest=None):
    from groups.invitations import usable
    if not usable(invitation) or invitation.email != email or (source_digest and invitation.token_digest != source_digest):
        return False
    actor = invitation.inviter
    target = invitation.group if kind == 'group' else invitation.activity
    return bool(actor and actor.is_active and actor.profile.email_verified_at
        and not actor.profile.outbound_mail_suspended and target.can_organize(actor)
        and not getattr(target, 'is_cancelled', False))


def pending_bridge(request, email):
    from activities.email_invitations import pending_invitation as pending_activity
    from groups.invitations import pending_invitation as pending_group
    for kind, invitation in [('activity', pending_activity(request)), ('group', pending_group(request))]:
        if valid_invitation(invitation, email, kind):
            return kind, invitation
    return None


def resolve(request, email, *, code='', existing=None):
    """No redemption/reservation here: abandonment, bad forms and mail failure don't burn access."""
    email = email.strip().lower()
    if code:
        admission = BetaAdmission.objects.filter(kind='code', verifier=verifier('code:'+code.strip())).first()
    elif existing:
        admission = BetaAdmission.objects.select_related('group_invitation__group', 'activity_invitation__activity').filter(pk=existing.pk).first()
    else:
        bridge = pending_bridge(request, email)
        if not bridge:
            raise ValidationError(ERROR)
        kind, invitation = bridge
        admission, _ = BetaAdmission.objects.get_or_create(kind=kind, source_digest=invitation.token_digest,
            defaults={'verifier':verifier(kind+':'+invitation.token_digest), 'email':email,
                kind+'_invitation':invitation, 'issued_by':invitation.inviter, 'expires_at':invitation.expires_at})
    if admission and admission.kind != 'code':
        lock_source(admission)
    if not valid(admission, email):
        raise ValidationError(ERROR)
    return admission


def redeem(admission, user):
    # Called inside the same serialized transaction as user creation and proof use.
    if not valid(admission, user.email.strip().lower()):
        raise ValidationError(ERROR)
    admission.redeemed_at = timezone.now()
    admission.redeemed_by = user
    admission.save(update_fields=['redeemed_at', 'redeemed_by'])


def lock_source(admission):
    if admission.kind == 'group' and admission.group_invitation_id:
        from groups.models import Group, GroupInvitation
        group_id = GroupInvitation.objects.filter(pk=admission.group_invitation_id).values_list('group_id', flat=True).first()
        Group.objects.select_for_update().filter(pk=group_id).first()
        admission.group_invitation = GroupInvitation.objects.select_for_update().select_related('group', 'inviter__profile').filter(pk=admission.group_invitation_id).first()
    elif admission.kind == 'activity' and admission.activity_invitation_id:
        from activities.models import Activity, ActivityEmailInvitation
        activity_id = ActivityEmailInvitation.objects.filter(pk=admission.activity_invitation_id).values_list('activity_id', flat=True).first()
        Activity.objects.select_for_update().filter(pk=activity_id).first()
        admission.activity_invitation = ActivityEmailInvitation.objects.select_for_update().select_related('activity', 'inviter__profile').filter(pk=admission.activity_invitation_id).first()
