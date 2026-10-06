"""Explicit legacy provisioning for pre-account-foundation test fixtures."""
from django.contrib.auth import get_user_model


def create_legacy_user(*args, **kwargs):
    user = get_user_model().objects.create_user(*args, **kwargs)
    user.profile.legacy_access = True
    user.profile.save(update_fields=['legacy_access'])
    return user
