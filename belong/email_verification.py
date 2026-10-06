"""One-time email proofs; no bearer tokens are stored in the database."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from social.models import EmailVerification, UserProfile


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def email_available(email, user=None):
    return not get_user_model().objects.filter(email__iexact=email).exclude(pk=getattr(user, 'pk', None)).exists()


def send_verification(request, user, email):
    email = email.strip().lower()
    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(user=user)
        now = timezone.now()
        recent = EmailVerification.objects.filter(user=user)
        if recent.filter(created_at__gt=now-timedelta(minutes=1)).exists() or recent.filter(created_at__gt=now-timedelta(hours=24)).count() >= 10:
            raise ValidationError('Please wait before requesting another verification email (one per minute, ten per day).')
        if not email_available(email, user):
            raise ValidationError('An account already uses this email. Sign in instead.')
        token = secrets.token_urlsafe(32)
        recent.filter(used_at__isnull=True).update(used_at=now)
        EmailVerification.objects.create(user=user, email=email, token_digest=digest(token), expires_at=now+timedelta(hours=24))
        profile.pending_email = email
        profile.save(update_fields=['pending_email'])
        url = request.build_absolute_uri(reverse('verify_email', args=[token]))
        if send_mail('Verify your Belong email', f'Confirm your email address: {url}\n\nThis one-time link expires in 24 hours.', None, [email], fail_silently=False) != 1:
            raise RuntimeError('Verification email was not delivered.')


def confirm_email(token):
    with transaction.atomic():
        proof = EmailVerification.objects.select_for_update().filter(token_digest=digest(token)).first()
        if not proof or proof.used_at or proof.expires_at <= timezone.now():
            raise ValidationError('This verification link has expired or was already used. Request a new one.')
        user = get_user_model().objects.select_for_update().get(pk=proof.user_id)
        profile = UserProfile.objects.select_for_update().get(user=user)
        if profile.pending_email != proof.email or not email_available(proof.email, user):
            raise ValidationError('This email is no longer available. Request a new verification link.')
        user.email = proof.email
        user.save(update_fields=['email'])
        profile.email_verified_at = timezone.now()
        profile.pending_email = ''
        profile.legacy_access = False
        profile.save(update_fields=['email_verified_at', 'pending_email', 'legacy_access'])
        proof.used_at = timezone.now()
        proof.save(update_fields=['used_at'])
        return user
