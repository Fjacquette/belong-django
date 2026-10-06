from django.shortcuts import redirect
from django.urls import reverse


class VerifiedEmailMiddleware:
    """Every product route, including direct POST and HTMX requests, requires access."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated and not request.user.profile.can_use_belong:
            allowed = {reverse('verification_status'), reverse('logout')}
            if request.path not in allowed and request.resolver_match.view_name not in {'verify_email', 'groups:invitation', 'groups:pending_invitation'}:
                response = redirect('verification_status')
                if request.headers.get('HX-Request') == 'true':
                    response['HX-Redirect'] = reverse('verification_status')
                return response
        return None
