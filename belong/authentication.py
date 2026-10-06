from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get('email') or '').strip()
        users = get_user_model().objects
        user = users.filter(email__iexact=identifier).first() if '@' in identifier else None
        if user is None and '@' not in identifier and settings.ALLOW_LEGACY_ACCOUNTS:
            user = users.filter(username=identifier, email='', profile__legacy_access=True).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        if user is None:
            get_user_model()().set_password(password)
