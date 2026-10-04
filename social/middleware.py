from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from .models import UserProfile


class ActivityPresenceMiddleware:
    """Authenticated HTTP activity, throttled to one write per minute; not socket presence."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            UserProfile.objects.filter(Q(last_active_at__isnull=True) | Q(last_active_at__lt=now-timedelta(minutes=1)), user=request.user).update(last_active_at=now)
        return self.get_response(request)
