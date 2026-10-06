from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import StyledAuthenticationForm, StyledUserCreationForm, InvitedUserCreationForm


class BrandLoginView(LoginView):
    form_class = StyledAuthenticationForm
    template_name = "registration/login.html"

    def get_success_url(self):
        from groups.invitations import finish_pending
        return finish_pending(self.request) or super().get_success_url()


def signup(request: HttpRequest) -> HttpResponse:
    from groups.invitations import find_invitation, usable, finish_pending
    invitation = find_invitation(request.session.get("group_invitation", ""))
    kwargs = {"invited_email": invitation.email} if usable(invitation) else {}
    form_class = InvitedUserCreationForm if kwargs else StyledUserCreationForm
    if request.method == "POST":
        form = form_class(request.POST, **kwargs)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(finish_pending(request) or "activities:index")
    else:
        form = form_class(**kwargs)

    return render(request, "registration/signup.html", {"form": form})
