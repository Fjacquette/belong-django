from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import StyledAuthenticationForm, StyledUserCreationForm


class BrandLoginView(LoginView):
    form_class = StyledAuthenticationForm
    template_name = "registration/login.html"


def signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = StyledUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("activities:index")
    else:
        form = StyledUserCreationForm()

    return render(request, "registration/signup.html", {"form": form})
