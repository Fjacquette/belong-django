"""Durable quota reservations. Commit before SMTP; failed delivery consumes quota."""
import hashlib
import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from social.models import EmailControlLock, OutboundEmailAttempt

logger = logging.getLogger(__name__)
OWN_MAIL_KINDS = ('signup', 'verification', 'recovery')


def address_hash(value):
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def request_ip_hash(request):
    # Never trust arbitrary X-Forwarded-For. Deployment must set REMOTE_ADDR safely.
    return address_hash(request.META.get('REMOTE_ADDR', 'unknown'))


def lock_controls():
    # Seeded in the migration, so no get-or-create race. Caller owns an atomic block.
    lock = EmailControlLock.objects.select_for_update().get(pk=1)
    lock.touched_at = timezone.now()
    lock.save(update_fields=['touched_at'])


def own_mail_reservation(request, email, kind, actor=None):
    """Caller holds the control lock; blocked attempts remain in the audit trail."""
    now = timezone.now()
    limits = settings.EMAIL_LIMITS
    recipient = address_hash(email)
    ip = request_ip_hash(request)
    attempts = OutboundEmailAttempt.objects.exclude(outcome='blocked')
    recent = attempts.filter(kind__in=OWN_MAIL_KINDS, created_at__gt=now-timedelta(hours=1))
    reason = ''
    if recent.filter(recipient_hash=recipient).count() >= limits['own_address_hour']:
        reason = 'address_hour'
    elif recent.filter(ip_hash=ip).count() >= limits['own_ip_hour']:
        reason = 'ip_hour'
    elif recent.filter(recipient_hash=recipient, created_at__gt=now-timedelta(seconds=limits['own_cooldown_seconds'])).exists():
        reason = 'address_cooldown'
    if actor and attempts.filter(kind__in=OWN_MAIL_KINDS, actor=actor, created_at__gt=now-timedelta(days=1)).count() >= limits['own_actor_day']:
        reason = 'actor_day'
    if kind == 'signup':
        signup = attempts.filter(kind='signup', ip_hash=ip)
        if signup.filter(created_at__gt=now-timedelta(hours=1)).count() >= limits['signup_ip_hour']:
            reason = 'signup_ip_hour'
        elif signup.filter(created_at__gt=now-timedelta(days=1)).count() >= limits['signup_ip_day']:
            reason = 'signup_ip_day'
    attempt = OutboundEmailAttempt.objects.create(kind=kind, actor=actor, recipient_hash=recipient,
        ip_hash=ip, outcome='blocked' if reason else 'reserved', reason=reason)
    return attempt if not reason else None


def reserve_own_mail(request, email, kind, actor=None):
    with transaction.atomic():
        lock_controls()
        return own_mail_reservation(request, email, kind, actor)


def owned_url(name, *args):
    origin = settings.BELONG_PUBLIC_ORIGIN
    if not origin and settings.ENVIRONMENT in {'dev', 'test'}:
        origin = 'http://127.0.0.1:' + ('8001' if settings.ENVIRONMENT == 'test' else '8000')
    parsed = urlsplit(origin)
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in {'', '/'} or parsed.query or parsed.fragment
            or (settings.ENVIRONMENT == 'production' and parsed.scheme != 'https')):
        raise ImproperlyConfigured('BELONG_PUBLIC_ORIGIN must be a canonical origin (HTTPS in production).')
    return origin.rstrip('/') + reverse(name, args=args)


def dispatch(attempt, subject, body, email):
    """Never call inside an atomic block: SMTP must not hold a database write lock."""
    from django.db import connection
    # TestCase has enclosing test transactions; production callers do not.
    if any(not getattr(block, '_from_testcase', False) for block in connection.atomic_blocks):
        raise RuntimeError('Email dispatch cannot run inside a write transaction.')
    outcome = 'sent'
    try:
        if send_mail(subject, body, None, [email], fail_silently=False) != 1:
            outcome = 'failed'
    except Exception as error:
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(reason=('delivery_' + type(error).__name__)[:80])
        # Do not log SMTP payloads, credentials, raw recipients or bearer URLs.
        outcome = 'failed'
    OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome=outcome)
    logger.info('outbound_email kind=%s actor=%s recipient_hash=%s attempt=%s outcome=%s',
                attempt.kind, attempt.actor_id, attempt.recipient_hash, attempt.pk, outcome)
    return outcome == 'sent'
