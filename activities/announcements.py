"""Context-only organizer updates, with a fixed delivery audience and live access checks."""
import uuid
from django import forms
from django.core import signing
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from groups.models import Group, MemberStatus
from .models import Activity, ActivityResponseStatus, Announcement
from .participation import locked_activity
from .visibility import visible_activities


class AnnouncementForm(forms.Form):
    submission_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, context=None, user=None, **kwargs):
        self.activity = context if isinstance(context, Activity) else None
        self.user = user
        super().__init__(*args, **kwargs)
        if self.activity and not self.is_bound:
            self.initial['submission_token'] = signing.dumps({'key': str(uuid.uuid4()), 'activity': context.pk, 'actor': user.pk}, salt='activity-update')

    def clean_submission_token(self):
        token = self.cleaned_data['submission_token']
        if not self.activity:
            return None
        try:
            payload = signing.loads(token, salt='activity-update', max_age=86400)
            if payload['activity'] != self.activity.pk or payload['actor'] != self.user.pk:
                raise ValueError
            return uuid.UUID(payload['key'])
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise forms.ValidationError('Reload this page before posting your update.')

    body = forms.CharField(max_length=2000, label='Update',
                           widget=forms.Textarea(attrs={'class': 'ui-field', 'rows': 4, 'maxlength': 2000}))


def updates_for(context, user, *, organizer):
    """A stored recipient list never grants access after participation/access is lost."""
    updates = context.announcements.select_related('author__profile')
    if organizer:
        return updates
    if isinstance(context, Group):
        allowed = context.memberships.filter(user=user, status=MemberStatus.ACTIVE).exists()
    else:
        allowed = (visible_activities(user).filter(pk=context.pk).exists()
                   and context.responses.filter(user=user).exclude(status=ActivityResponseStatus.DECLINED).exists())
    return updates.filter(recipients=user) if allowed else updates.none()


def update_context(request, context, *, organizer):
    page = Paginator(updates_for(context, request.user, organizer=organizer), 20).get_page(request.GET.get('updates_page'))
    return {'announcements': page, 'can_announce': organizer,
            'announcement_url': context_announcement_url(context)}


def context_announcement_url(context):
    route = 'groups:announce' if isinstance(context, Group) else 'activities:announce'
    return reverse(route, args=[context.pk])


def _render_compose(request, context, form):
    is_group = isinstance(context, Group)
    return render(request, 'activities/announcement_form.html', {
        'context_object': context, 'form': form, 'is_group': is_group,
        'back_url': context.get_absolute_url() if is_group else reverse('activities:roster', args=[context.pk]),
        'suppress_create': True,
    })


def _publish(request, context, form):
    if not context.can_organize(request.user):
        raise Http404
    if isinstance(context, Group):
        recipients = set(context.memberships.filter(status=MemberStatus.ACTIVE).values_list('user_id', flat=True))
        recipients.add(context.owner_id)
        scope = {'group': context}
    else:
        recipients = set(context.responses.exclude(status=ActivityResponseStatus.DECLINED).values_list('user_id', flat=True))
        scope = {'activity': context}
    key = form.cleaned_data.get('submission_token') if isinstance(context, Activity) else None
    if key and Announcement.objects.filter(submission_key=key).exists():
        return
    announcement = Announcement.objects.create(author=request.user, body=form.cleaned_data['body'], submission_key=key, **scope)
    announcement.recipients.set(recipients)
    if isinstance(context, Activity):
        from .notifications import queue_event
        queue_event(context, request.user, 'update', announcement=announcement)


@login_required
@require_http_methods(['GET', 'POST'])
def activity_announce(request, pk):
    context = get_object_or_404(Activity.objects.select_related('group'), pk=pk)
    if not context.can_organize(request.user):
        raise Http404
    form = AnnouncementForm(request.POST if request.method == 'POST' else None, context=context, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with locked_activity(pk) as context:
            _publish(request, context, form)
        return redirect('activities:roster', pk=pk)
    return _render_compose(request, context, form)


@login_required
@require_http_methods(['GET', 'POST'])
def group_announce(request, pk):
    context = get_object_or_404(Group, pk=pk)
    if not context.can_organize(request.user):
        raise Http404
    form = AnnouncementForm(request.POST if request.method == 'POST' else None, context=context, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            context = Group.objects.select_for_update().get(pk=pk)
            _publish(request, context, form)
        return redirect(context)
    return _render_compose(request, context, form)
