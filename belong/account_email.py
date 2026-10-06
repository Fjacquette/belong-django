"""Public email requests and owner-only signup/recovery completion."""
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from social.models import AccountEmailProof, EmailVerification, OutboundEmailAttempt
from .email_controls import lock_controls, own_mail_reservation, owned_url, dispatch, request_ip_hash, address_hash
from .email_verification import digest


def request_account_email(request, email, purpose):
    if purpose not in {'signup', 'recovery'}:
        raise ValueError('Unsupported account email purpose.')
    email = email.strip().lower()
    with transaction.atomic():
        lock_controls()
        attempt = own_mail_reservation(request, email, purpose)
        if attempt is None:
            return
        user = get_user_model().objects.filter(email__iexact=email).first()
        claimable = user is None or (user.is_active and not user.profile.email_verified_at and not user.profile.legacy_access)
        if claimable and (purpose == 'signup' or user is not None):
            token = secrets.token_urlsafe(32)
            # Keep earlier links valid until one succeeds; retries cannot invalidate an owner's inbox.
            AccountEmailProof.objects.create(email=email, purpose='signup', token_digest=digest(token), expires_at=timezone.now()+timedelta(hours=24))
            route = ('complete_signup', token)
        elif purpose == 'recovery' and user and user.is_active:
            token = secrets.token_urlsafe(32)
            AccountEmailProof.objects.create(email=email, purpose=purpose, user=user, token_digest=digest(token), expires_at=timezone.now()+timedelta(hours=1))
            route = ('complete_recovery', token)
        else:
            route = ('login',) if purpose == 'signup' else ('signup',)
    try:
        url = owned_url(*route)
    except Exception:
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='failed', reason='origin_configuration')
        return
    # Always one fixed transactional message for an allowed public request, even
    # for unknown recovery addresses. Lookup results never change HTTP/cookie behavior.
    subject = 'Your Belong account link'
    body = f'You requested help accessing Belong.\n\nContinue with Belong: {url}\n\nIf you did not request this, ignore this message. Account setup links expire in 24 hours; recovery links expire in 1 hour.'
    dispatch(attempt, subject, body, email)


def valid_proof(token, purpose):
    return AccountEmailProof.objects.filter(token_digest=digest(token), purpose=purpose,
        used_at__isnull=True, expires_at__gt=timezone.now()).first()


def creation_allowed(request):
    now = timezone.now()
    ip = request_ip_hash(request)
    attempts = OutboundEmailAttempt.objects.filter(kind='account_creation', ip_hash=ip, outcome='created')
    from django.conf import settings
    return (attempts.filter(created_at__gt=now-timedelta(hours=1)).count() < settings.EMAIL_LIMITS['creation_ip_hour']
            and attempts.filter(created_at__gt=now-timedelta(days=1)).count() < settings.EMAIL_LIMITS['creation_ip_day'])


def complete_signup(request, token, data):
    with transaction.atomic():
        lock_controls()
        proof = valid_proof(token, 'signup')
        if proof is None:
            raise ValidationError('This link has expired or was already used. Request another account link.')
        user = get_user_model().objects.select_for_update().filter(email__iexact=proof.email).first()
        if user and (not user.is_active or user.profile.email_verified_at or user.profile.legacy_access):
            raise ValidationError('Please sign in or request account recovery to continue.')
        if user is None:
            if not creation_allowed(request):
                raise ValidationError('Please wait before creating another account. You can use this link later.')
            user = get_user_model().objects.create_user('u_'+uuid.uuid4().hex, email=proof.email)
            OutboundEmailAttempt.objects.create(kind='account_creation', actor=user,
                recipient_hash=address_hash(proof.email), ip_hash=request_ip_hash(request), outcome='created')
        # The proven owner replaces provisional credentials/identity, keeping a stable PK.
        user.set_password(data['password1'])
        user.save(update_fields=['password'])
        profile = user.profile
        profile.email_verified_at = timezone.now()
        profile.legacy_access = False
        profile.pending_email = ''
        profile.display_name = data['display_name']
        profile.account_type = data['account_type']
        profile.interests_prompt_pending = True
        profile.save(update_fields=['email_verified_at', 'legacy_access', 'pending_email', 'display_name', 'account_type', 'interests_prompt_pending'])
        # Invalidate all proofs for this address, including old provisional-account proofs.
        AccountEmailProof.objects.filter(email__iexact=proof.email, used_at__isnull=True).update(used_at=timezone.now())
        EmailVerification.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        return user


def complete_recovery(token, password):
    with transaction.atomic():
        lock_controls()
        proof = valid_proof(token, 'recovery')
        user = get_user_model().objects.select_for_update().filter(pk=getattr(proof, 'user_id', None), is_active=True).first()
        if not proof or not user or user.email.strip().lower() != proof.email:
            raise ValidationError('This link has expired or was already used. Request another account link.')
        if not user.profile.email_verified_at and not user.profile.legacy_access:
            raise ValidationError('Request an account setup link to complete your identity and password.')
        user.set_password(password)
        user.save(update_fields=['password'])
        # Control of the canonical address also completes an old provisional signup.
        profile = user.profile
        profile.email_verified_at = timezone.now()
        profile.pending_email = ''
        profile.legacy_access = False
        profile.save(update_fields=['email_verified_at', 'pending_email', 'legacy_access'])
        AccountEmailProof.objects.filter(email__iexact=proof.email, used_at__isnull=True).update(used_at=timezone.now())
        EmailVerification.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        return user
