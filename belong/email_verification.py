"""One-time email proofs; no bearer tokens are stored in the database."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from social.models import EmailVerification, UserProfile


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def email_available(email, user=None):
    return not get_user_model().objects.filter(email__iexact=email).exclude(pk=getattr(user, 'pk', None)).exists()


def send_verification(request, user, email):
    from .email_controls import lock_controls, own_mail_reservation, owned_url, dispatch
    email = email.strip().lower()
    with transaction.atomic():
        lock_controls()
        profile = UserProfile.objects.select_for_update().get(user=user)
        canonical = user.email.strip().lower() or profile.pending_email
        denied_target = ((not profile.email_verified_at and canonical and canonical != email)
                         or (profile.outbound_mail_suspended and canonical != email))
        if denied_target:
            from social.models import OutboundEmailAttempt
            from .email_controls import address_hash, request_ip_hash
            OutboundEmailAttempt.objects.create(kind='verification', actor=user,
                recipient_hash=address_hash(email), ip_hash=request_ip_hash(request),
                outcome='blocked', reason='outbound_suspended' if profile.outbound_mail_suspended else 'not_own_address')
            attempt = None
        else:
            attempt = own_mail_reservation(request, email, 'verification', user)
        if attempt is not None:
            token = secrets.token_urlsafe(32)
            # Earlier links remain valid until completion, but only the current
            # pending address can be confirmed. Failed sends never auto-retry.
            EmailVerification.objects.create(user=user, email=email, token_digest=digest(token), expires_at=timezone.now()+timedelta(hours=24))
            profile.pending_email = email
            profile.save(update_fields=['pending_email'])
    if attempt is None:
        if denied_target and profile.outbound_mail_suspended:
            raise ValidationError('Outbound email changes are suspended for this account.')
        raise ValidationError('Please wait or verify your current address before requesting another account email.')
    try:
        url = owned_url('verify_email', token)
    except Exception:
        from social.models import OutboundEmailAttempt
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='failed', reason='origin_configuration')
        raise ValidationError('Account email could not be sent. Please retry later.')
    if not dispatch(attempt, 'Verify your Belong email', f'Confirm your email address: {url}\n\nThis one-time link expires in 24 hours.', email):
        raise ValidationError('Account email could not be sent. Please retry later.')


def confirm_email(token):
    from .email_controls import lock_controls
    with transaction.atomic():
        lock_controls()
        proof = EmailVerification.objects.select_for_update().filter(token_digest=digest(token)).first()
        if not proof or proof.used_at or proof.expires_at <= timezone.now():
            raise ValidationError('This verification link has expired or was already used. Request a new one.')
        user = get_user_model().objects.select_for_update().get(pk=proof.user_id)
        profile = UserProfile.objects.select_for_update().get(user=user)
        if not profile.email_verified_at and not profile.legacy_access:
            raise ValidationError('Request an account setup link to choose your own password and verify this address.')
        if profile.pending_email != proof.email or not email_available(proof.email, user):
            raise ValidationError('This email is no longer available. Request a new verification link.')
        user.email = proof.email
        user.save(update_fields=['email'])
        profile.email_verified_at = timezone.now()
        profile.pending_email = ''
        profile.legacy_access = False
        profile.save(update_fields=['email_verified_at', 'pending_email', 'legacy_access'])
        proof.used_at = timezone.now()
        EmailVerification.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        return user
