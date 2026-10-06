from django.shortcuts import redirect
from django.urls import reverse


class VerifiedEmailMiddleware:
    """Every product route, including direct POST and HTMX requests, requires access."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.profile.can_use_belong:
            allowed = {reverse('verification_status'), reverse('logout')}
            if request.path not in allowed and not request.path.startswith('/accounts/verify/'):
                response = redirect('verification_status')
                if request.headers.get('HX-Request') == 'true':
                    response['HX-Redirect'] = reverse('verification_status')
                return response
        return self.get_response(request)
