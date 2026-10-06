import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordChangeDoneView
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import StyledAuthenticationForm, StyledUserCreationForm, InvitedUserCreationForm, ProfileForm, EmailChangeForm, VerificationEmailForm, InterestsForm, style_fields
from .email_verification import send_verification, confirm_email

logger = logging.getLogger(__name__)


def deliver(request, user, email, form=None):
    try:
        send_verification(request, user, email)
    except (ValidationError, IntegrityError) as error:
        text = error.messages[0] if isinstance(error, ValidationError) else 'This email is no longer available.'
        if form is not None:
            form.add_error(None, text)
        else:
            messages.error(request, text)
        return False
    except Exception:
        logger.exception('Verification delivery failed for user %s', user.pk)
        messages.error(request, 'Verification email could not be sent. Please retry.')
        return False
    messages.success(request, 'Verification email sent. Check your inbox.')
    return True


class BrandLoginView(LoginView):
    form_class = StyledAuthenticationForm
    template_name = 'registration/login.html'

    def get_success_url(self):
        if not self.request.user.profile.can_use_belong:
            return reverse_lazy('verification_status')
        return after_verification(self.request, super().get_success_url())


@require_http_methods(['GET', 'POST'])
def signup(request):
    from groups.invitations import pending_invitation, usable
    if request.user.is_authenticated:
        return redirect('activities:index' if request.user.profile.can_use_belong else 'verification_status')
    invitation = pending_invitation(request)
    kwargs = {'invited_email': invitation.email} if usable(invitation) else {}
    form_class = InvitedUserCreationForm if kwargs else StyledUserCreationForm
    form = form_class(request.POST or None, **kwargs)
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            form.add_error('email', 'An account already uses this email. Sign in instead.')
        else:
            login(request, user, backend='belong.authentication.EmailBackend')
            deliver(request, user, user.email)
            return redirect('verification_status')
    return render(request, 'registration/signup.html', {'form': form, 'suppress_create': True})


@login_required
@require_http_methods(['GET', 'POST'])
def verification_status(request):
    if request.user.profile.can_use_belong:
        return redirect(after_verification(request))
    profile = request.user.profile
    from groups.invitations import pending_invitation, usable
    invitation = pending_invitation(request)
    invited = usable(invitation) and invitation.email == request.user.email.strip().lower()
    form = VerificationEmailForm(request.POST or None, initial={'email': profile.pending_email or request.user.email})
    if invited:
        # Registration's invited email is immutable; proof and invite context stay aligned.
        form.fields['email'].widget.attrs['readonly'] = True
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if invited and email != request.user.email:
            form.add_error('email', 'Use the invited email address.')
        elif deliver(request, request.user, email, form):
            return redirect('verification_status')
    response = render(request, 'registration/verification_status.html', {'form': form, 'suppress_create': True})
    response['Cache-Control'] = 'no-store'
    return response


@require_http_methods(['GET', 'POST'])
def verify_email(request, token):
    error = None
    if request.method == 'POST':
        try:
            user = confirm_email(token)
        except (ValidationError, IntegrityError) as exc:
            error = exc.messages[0] if isinstance(exc, ValidationError) else 'This email is no longer available. Request a new link.'
        else:
            messages.success(request, 'Email verified.')
            if request.user.is_authenticated and request.user.pk == user.pk:
                # Refresh the cached profile after confirmation.
                request.user.refresh_from_db()
                return redirect(after_verification(request))
            return redirect('login')
    response = render(request, 'registration/verify_email.html', {'error': error, 'suppress_create': True})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'same-origin'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def account_settings(request):
    profile = request.user.profile
    action = request.POST.get('action')
    profile_form = ProfileForm(request.POST if action == 'profile' else None, request.FILES if action == 'profile' else None, instance=profile)
    email_form = EmailChangeForm(request.POST if action == 'email' else None, user=request.user)
    if request.method == 'POST':
        if action == 'profile' and profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Profile saved.')
            return redirect('account_settings')
        if action == 'email' and email_form.is_valid() and deliver(request, request.user, email_form.cleaned_data['email'], email_form):
            return redirect('account_settings')
        if action == 'resend' and profile.pending_email:
            deliver(request, request.user, profile.pending_email)
            return redirect('account_settings')
    response = render(request, 'registration/account_settings.html', {'profile_form': profile_form, 'email_form': email_form, 'suppress_create': True})
    response['Cache-Control'] = 'no-store'
    return response


class BrandPasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('password_change_done')
    extra_context = {'suppress_create': True}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        style_fields(form)
        return form


class BrandPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'registration/password_change_done.html'
    extra_context = {'suppress_create': True}


def after_verification(request, fallback='account_settings'):
    from groups.invitations import finish_pending
    destination = finish_pending(request)
    if request.user.profile.interests_prompt_pending:
        if destination:
            # Only a server-generated invitation destination is stored, never a supplied URL.
            request.session['interests_return'] = destination
        return reverse('account_interests')
    return destination or fallback


@login_required
@require_http_methods(['GET', 'POST'])
def account_interests(request):
    profile = request.user.profile
    onboarding = profile.interests_prompt_pending
    form = InterestsForm(request.POST if request.method == 'POST' else None, profile=profile)
    if request.method == 'POST':
        if request.POST.get('action') == 'skip' and onboarding:
            profile.interests_prompt_pending = False
            profile.save(update_fields=['interests_prompt_pending'])
            return redirect(request.session.pop('interests_return', None) or 'activities:index')
        if form.is_valid():
            form.save()
            messages.success(request, 'Interests saved.')
            return redirect(request.session.pop('interests_return', None) or ('activities:index' if onboarding else 'account_settings'))
    # Group canonical form choices without introducing a second set of submitted inputs.
    sections = {}
    for choice, interest in zip(form['interests'], form.fields['interests'].queryset):
        sections.setdefault(interest.section or 'Other interests', []).append(choice)
    response = render(request, 'registration/interests.html', {
        'form': form, 'sections': sections, 'onboarding': onboarding, 'suppress_create': True,
    })
    response['Cache-Control'] = 'no-store'
    return response
