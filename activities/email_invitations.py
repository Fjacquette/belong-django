"""Email-bound Activity invitations reuse shared delivery controls, never Group admission."""
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from belong.email_controls import lock_controls, invitation_reservation, invitation_error, owned_url, dispatch
from groups.invitations import digest, usable
from social.models import OutboundEmailAttempt
from .models import Activity, ActivityEmailInvitation, ActivityInvitation
from .participation import locked_activity
from .visibility import visible_activities


def find_invitation(token):
    return ActivityEmailInvitation.objects.select_related('activity', 'inviter__profile').filter(token_digest=digest(token)).first()


def issue_invitation(activity, inviter, email, request):
    email = email.strip().lower()
    validate_email(email)
    with transaction.atomic():
        lock_controls()
        activity = Activity.objects.select_for_update().get(pk=activity.pk)
        attempt, reason = invitation_reservation(request, inviter, email, activity=activity)
        if not reason and activity.direct_invitations.filter(user__email__iexact=email).exists():
            attempt.outcome = 'not_needed'
            attempt.save(update_fields=['outcome'])
            return False
        if not reason:
            token = secrets.token_urlsafe(32)
            ActivityEmailInvitation.objects.update_or_create(activity=activity, email=email, defaults={
                'inviter': inviter, 'token_digest': digest(token), 'status': 'pending',
                'expires_at': timezone.now()+timedelta(days=7), 'accepted_by': None, 'accepted_at': None,
            })
    if reason:
        raise invitation_error(reason)
    try:
        url = owned_url('activities:email_invitation', token)
    except Exception:
        OutboundEmailAttempt.objects.filter(pk=attempt.pk).update(outcome='failed', reason='origin_configuration')
        raise ValidationError('Invitation email could not be sent. Please retry later.')
    # Fixed text avoids an arbitrary-content relay and never discloses private Activity data.
    if not dispatch(attempt, 'Your Belong activity invitation',
                    f'You have been invited to an activity on Belong.\n\nReview and accept: {url}\n\n'
                    'This invitation expires in seven days. Use this email address to sign in or create an account. '
                    'Accepting does not RSVP or join a Group. Activity audience rules still apply.', email):
        raise ValidationError('Invitation email could not be sent. Please retry later.')
    return True


def pending_invitation(request):
    reference = request.session.get('pending_activity_invitation')
    if not isinstance(reference, int) or isinstance(reference, bool):
        return None
    return ActivityEmailInvitation.objects.select_related('activity', 'inviter__profile').filter(pk=reference).first()


def accept_reference(reference, user):
    # Internal only: reference originates in a validated bearer link or signed session.
    activity_id = ActivityEmailInvitation.objects.filter(pk=reference).values_list('activity_id', flat=True).first()
    if activity_id is None:
        raise ValidationError('This invitation is unavailable.')
    try:
        with locked_activity(activity_id) as activity:
            invitation = ActivityEmailInvitation.objects.select_for_update().filter(pk=reference).first()
            if invitation is None:
                raise ValidationError('This invitation is unavailable.')
            user = get_user_model().objects.select_for_update().get(pk=user.pk)
            if not user.is_active or user.email.strip().lower() != invitation.email:
                raise ValidationError('Sign in with the account that uses the invited email address.')
            consumed = invitation.status == 'accepted' and invitation.accepted_by_id == user.pk
            if not consumed and not usable(invitation):
                raise ValidationError('This invitation has expired or is no longer available.')
            if not user.profile.can_use_belong:
                raise ValidationError('Verify your email before accepting this invitation.')
            if not visible_activities(user).filter(pk=activity.pk).exists():
                raise ValidationError('This activity is not available to your account. An invitation does not change its audience; contact the organizer.')
            if consumed:
                # A used token cannot recreate a direct invitation removed by its organizer.
                return activity if activity.direct_invitations.filter(user=user).exists() else None
            if not user.profile.email_verified_at:
                user.profile.email_verified_at = timezone.now()
                user.profile.legacy_access = False
                user.profile.save(update_fields=['email_verified_at', 'legacy_access'])
            ActivityInvitation.objects.get_or_create(activity=activity, user=user, defaults={'invited_by': invitation.inviter})
            invitation.status = 'accepted'
            invitation.accepted_by = user
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['status', 'accepted_by', 'accepted_at', 'updated_at'])
            return activity
    except Activity.DoesNotExist as error:
        raise ValidationError('This invitation is unavailable.') from error


def finish_pending(request):
    invitation = pending_invitation(request)
    if invitation is None:
        request.session.pop('pending_activity_invitation', None)
        return None
    try:
        activity = accept_reference(invitation.pk, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return reverse('activities:pending_email_invitation')
    request.session.pop('pending_activity_invitation', None)
    messages.success(request, 'Activity invitation accepted. You can now RSVP.' if activity else 'This invitation was already used.')
    return activity.get_absolute_url() if activity else reverse('activities:index')


@require_http_methods(['GET', 'POST'])
def invitation(request, token):
    return _invitation_response(request, find_invitation(token))


@require_http_methods(['GET', 'POST'])
def pending_invitation_view(request):
    return _invitation_response(request, pending_invitation(request))


def _invitation_response(request, invitation):
    available = bool(usable(invitation))
    matched = bool(request.user.is_authenticated and invitation and request.user.email.strip().lower() == invitation.email)
    accessible = bool(available and matched and request.user.profile.can_use_belong
                      and visible_activities(request.user).filter(pk=invitation.activity_id).exists())
    if request.method == 'POST':
        if request.POST.get('auth') == 'switch' and available:
            logout(request)
            request.session['pending_activity_invitation'] = invitation.pk
            return redirect('login')
        if not request.user.is_authenticated:
            if not available:
                return _render_invitation(request, available=False, matched=False, invitation=None)
            request.session['pending_activity_invitation'] = invitation.pk
            return redirect('signup' if request.POST.get('auth') == 'signup' else 'login')
        if available and matched and not request.user.profile.can_use_belong:
            request.session['pending_activity_invitation'] = invitation.pk
            return redirect('verification_status')
        try:
            activity = accept_reference(invitation.pk if invitation else None, request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            request.session.pop('pending_activity_invitation', None)
            return redirect(activity or 'activities:index')
    return _render_invitation(request, available=available, matched=matched,
                              invitation=invitation if accessible else None)


def _render_invitation(request, **context):
    response = render(request, 'activities/email_invitation.html', {**context, 'suppress_create': True})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'same-origin'
    return response


@login_required
@require_POST
def send_invitation(request, pk):
    from .invitations import EmailInviteForm
    from .views import _organizer_activity, _render_roster
    activity = _organizer_activity(request.user, pk)
    form = EmailInviteForm(request.POST)
    if not form.is_valid():
        return _render_roster(request, activity, email_invite_form=form)
    try:
        sent = issue_invitation(activity, request.user, form.cleaned_data['email'], request)
    except ValidationError as error:
        form.add_error(None, error.messages[0])
        return _render_roster(request, activity, email_invite_form=form)
    messages.success(request, 'Activity invitation sent.' if sent else 'This person already has a direct invitation.')
    return redirect('activities:roster', pk=pk)


@login_required
@require_POST
def revoke_invitation(request, pk, invitation_pk):
    from .views import _organizer_activity
    _organizer_activity(request.user, pk)
    with locked_activity(pk) as activity:
        if not activity.can_organize(request.user):
            from django.http import Http404
            raise Http404
        invitation = get_object_or_404(activity.email_invitations.select_for_update(), pk=invitation_pk)
        if invitation.status == 'pending':
            invitation.status = 'revoked'
            invitation.save(update_fields=['status', 'updated_at'])
    return redirect('activities:roster', pk=pk)
