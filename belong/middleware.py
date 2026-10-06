from django.shortcuts import redirect
from django.urls import reverse


class VerifiedEmailMiddleware:
    """Every product route, including direct POST and HTMX requests, requires access."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        from social.models import UserProfile
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            # Repair missing identity data without granting verified/legacy access.
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            request.user.profile = profile
        if not profile.can_use_belong:
            allowed = {reverse('verification_status'), reverse('logout')}
            if request.path not in allowed and request.resolver_match.view_name not in {'verify_email', 'complete_signup', 'complete_recovery', 'password_reset', 'account_email_requested', 'groups:invitation', 'groups:pending_invitation'}:
                response = redirect('verification_status')
                if request.headers.get('HX-Request') == 'true':
                    response['HX-Redirect'] = reverse('verification_status')
                return response
        return None
