"""Contextual consent for the existing global Activity email preference."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .participation import locked_activity
from .polls import recipient_ids
from .visibility import visible_activities


def email_offer(user, activity, *, ignore_preference=False):
    """Reuse participant authority; votes, invitations and pending requests aren't consent."""
    profile = user.profile
    if (not user.is_active or not profile.email_verified_at
            or (profile.activity_email_enabled and not ignore_preference)
            or activity.is_cancelled):
        return None
    try:
        validate_email(user.email)
    except ValidationError:
        return None
    if (user.pk not in recipient_ids(activity)
            or not visible_activities(user).filter(pk=activity.pk).exists()):
        return None
    return activity


@login_required
@require_POST
def enable(request, pk):
    get_object_or_404(visible_activities(request.user), pk=pk)
    with locked_activity(pk) as activity:
        # Recheck current participation/access before consent. Repeated requests are
        # harmless, but cannot enable consent after removal/decline/cancellation.
        was_enabled = request.user.profile.activity_email_enabled
        if not email_offer(request.user, activity, ignore_preference=True):
            raise Http404
        request.user.profile.activity_email_enabled = True
        if not was_enabled:
            type(request.user.profile).objects.filter(pk=request.user.profile.pk).update(activity_email_enabled=True)
    notice = 'Activity update and cancellation emails are on for Activities you participate in. You can turn them off in Account settings.'
    from .views import _participation_next_path, _render_join_region
    if request.headers.get('HX-Request') == 'true':
        if request.POST.get('variant') == 'detail':
            return _render_join_region(request, activity, notice)
        return render(request, 'activities/_email_opt_in.html', {'email_notice': notice})
    messages.success(request, notice)
    return redirect(_participation_next_path(request, activity))
