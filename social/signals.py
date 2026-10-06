from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):  # pragma: no cover - simple signal
    if created:
        UserProfile.objects.create(user=instance, display_name=instance.get_full_name() or instance.username,
                                   legacy_access=settings.ALLOW_LEGACY_ACCOUNTS and not instance.username.startswith('u_'))
    else:
        UserProfile.objects.get_or_create(user=instance)
