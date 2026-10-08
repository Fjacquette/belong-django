"""Private occurrence drafts, with an explicit copy allowlist and atomic publication."""
from copy import deepcopy
from decimal import Decimal
from datetime import datetime
import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import ActivityForm
from .models import Activity, ActivityDraft, ActivitySeries, DEFAULT_RESPONSE_CHOICES, current_response_values
from .visibility import visible_activities

# Deliberately independent of model fields / Series defaults: new fields never
# silently become copied state. Schedule, invitation identities and lifecycle are absent.
COPY_FIELDS = (
    'title', 'headline', 'summary', 'description', 'category', 'location_type',
    'location_url', 'location_name', 'location_address1', 'location_address2',
    'location_city', 'location_state', 'location_zip', 'location_phone', 'location_gps',
    'location_instructions', 'organizer_name', 'organizer_image', 'audience',
    'allow_friend_invites', 'allow_friend_of_friend_invites', 'cost_type', 'cost_amount',
    'cost_display', 'cost_has_details', 'accommodations', 'restrictions', 'header_image',
    'color_primary', 'color_secondary', 'action1_label', 'action1_url', 'action2_label',
    'action2_url', 'action3_label', 'action3_url', 'available_responses', 'capacity',
    'participation_config',
)
EXTRA_FIELDS = ('participation_pattern', 'registration_admission', 'registration_allocation',
    'registration_reservations', 'registration_waitlist', 'poll_date_1', 'poll_date_2', 'poll_date_3')


def json_value(value):
    if isinstance(value, (Decimal, datetime)):
        return str(value) if isinstance(value, Decimal) else value.isoformat()
    if hasattr(value, 'pk'):
        return str(value.pk)
    # UUID image identities are stored as strings without copying their bytes.
    return json.loads(json.dumps(value, default=str))


def source_for(user, pk):
    source = get_object_or_404(visible_activities(user).select_related('group', 'series'), pk=pk)
    if not source.can_organize(user):
        raise Http404
    return source


def copy_values(source, user):
    values = {name: json_value(deepcopy(getattr(source, source._meta.get_field(name).attname))) for name in COPY_FIELDS}
    values['available_responses'] = current_response_values(source.available_responses) or list(DEFAULT_RESPONSE_CHOICES)
    values.update(starts_at=None, ends_at=None, post_until=None, freetext_when='', multiple_events=False,
        invite_group_members=False, group=None, series=None)
    if source.group_id and source.group.can_organize(user):
        values['group'] = source.group_id
    if source.series_id and source.series.can_organize(user) and source.series.group_id == values['group']:
        values['series'] = source.series_id
    # Copy authored occurrence settings, never reapply today's Series defaults.
    values['participation_pattern'] = source.participation_config['pattern'] if source.participation_config else ''
    if source.is_free_ongoing:
        from .models import OngoingOpportunity
        opportunity = OngoingOpportunity.objects.filter(activity=source).first()
        values['capacity'] = opportunity.capacity if opportunity else None
    if source.is_registration:
        target = getattr(source, 'registration_target', None)
        if target:
            values.update(capacity=target.capacity, registration_admission=target.admission,
                registration_allocation=target.allocation)
            pool = getattr(target, 'reservation_pool', None)
            if pool:
                values.update(capacity=pool.capacity, registration_reservations=True,
                    registration_waitlist=pool.waitlist_enabled)
    values['interests'] = list(source.interests.values_list('pk', flat=True))
    return values


class DraftForm(ActivityForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, draft, user, **kwargs):
        self.draft = draft
        values = deepcopy(draft.values)
        from django.utils.dateparse import parse_datetime
        for name in ('starts_at', 'ends_at', 'post_until', 'poll_date_1', 'poll_date_2', 'poll_date_3'):
            if values.get(name):
                values[name] = parse_datetime(values[name])
        # A fresh Activity permits changing the pattern without weakening published
        # Activity configuration immutability. No source instance is ever form-bound.
        super().__init__(*args, user=user, initial={**values, 'revision': draft.revision},
            instance=Activity(participation_config=deepcopy(values.get('participation_config'))), **kwargs)
        groups = self.fields['group'].queryset
        self.fields['series'] = forms.ModelChoiceField(required=False,
            queryset=ActivitySeries.objects.filter(Q(owner=user, group__isnull=True) | Q(group__in=groups)).distinct(),
            label='Series (optional)', widget=forms.Select(attrs={'class':'ui-field'}),
            help_text='Association only. This draft uses copied occurrence values, not current Series defaults.')
        config = values.get('participation_config')
        if config and config['pattern'] not in dict(self.fields['participation_pattern'].choices):
            self.fields['participation_pattern'].choices = list(self.fields['participation_pattern'].choices) + [(config['pattern'], self.instance.participation_pattern_label)]
            self.fields['participation_pattern'].disabled = True
        self.sections = []
        sections = (
            ('Hike details', ('title', 'description', 'starts_at', 'ends_at', 'location_name', 'location_instructions', 'capacity', 'audience')),
            ('Group, Series and invitations', ('group', 'series', 'invite_group_members', 'allow_friend_invites', 'allow_friend_of_friend_invites')),
            ('Participation', ('participation_pattern',) + EXTRA_FIELDS[1:] + ('available_responses',)),
            ('More logistics and cost', ('location_type', 'location_url', 'location_address1', 'location_address2', 'location_city', 'location_state', 'location_zip', 'location_phone', 'location_gps', 'cost_type', 'cost_amount', 'cost_display', 'cost_has_details', 'accommodations', 'restrictions', 'freetext_when', 'multiple_events', 'post_until')),
            ('Artwork and additional details', ('headline', 'summary', 'category', 'organizer_name', 'organizer_image', 'header_image', 'color_primary', 'color_secondary', 'action1_label', 'action1_url', 'action2_label', 'action2_url', 'action3_label', 'action3_url')),
        )
        for label, names in sections:
            fields = [self[name] for name in names]
            self.sections.append({'label':label, 'fields':fields, 'open':not self.is_bound or any(field.errors for field in fields)})

    def clean(self):
        data = super().clean()
        if data.get('revision') != self.draft.revision:
            self.add_error(None, 'This draft changed in another tab. Reload before saving or publishing.')
        series = data.get('series')
        if series and series.group_id != getattr(data.get('group'), 'pk', None):
            self.add_error('series', 'Choose the Series associated with this Group, or remove the Series.')
        start, end = data.get('starts_at'), data.get('ends_at')
        if start and end and end <= start:
            self.add_error('ends_at', 'End time must be after the start time.')
        return data

    def validate_publication(self):
        data = self.cleaned_data
        pattern = data.get('participation_pattern')
        if (pattern == 'scheduled' or (self.draft.requires_schedule and not pattern)) and not data.get('starts_at'):
            self.add_error('starts_at', 'Choose a new date and time before publishing this outing.')
        for name in ('starts_at', 'ends_at', 'post_until'):
            if data.get(name) and data[name] <= timezone.now():
                self.add_error(name, 'Choose a future date and time before publishing.')
        return not self.errors

    def copied_values(self):
        data = self.cleaned_data
        result = {name: json_value(data.get(name)) for name in ActivityForm.Meta.fields}
        result.update({name: json_value(data.get(name)) for name in EXTRA_FIELDS})
        result['participation_config'] = deepcopy(self.instance.participation_config)
        # These are deliberately separate pools, configured only upon publication.
        if self.instance.is_free_ongoing:
            result['capacity'] = data.get('cohort_capacity')
        if self.instance.is_registration:
            result['capacity'] = data['registration_terms']['capacity']
        result['series'] = getattr(data.get('series'), 'pk', None)
        result['interests'] = self.draft.values.get('interests', [])
        return result


def publish_capabilities(activity, data):
    if activity.is_date_planning:
        from .polls import create_poll
        create_poll(activity, [data[f'poll_date_{n}'] for n in range(1,4)])
    if activity.is_free_ongoing:
        from .models import OngoingOpportunity
        OngoingOpportunity.objects.create(activity=activity, capacity=data.get('cohort_capacity'))
    if activity.is_registration:
        from .models import RegistrationTarget, FreeReservationPool
        target = RegistrationTarget.objects.create(activity=activity, **data['registration_terms'])
        if data.get('registration_reservations'):
            FreeReservationPool.objects.create(target=target, capacity=target.capacity,
                waitlist_enabled=data.get('registration_waitlist', False))


@login_required
@require_GET
def history(request):
    groups = ActivityForm(user=request.user).fields['group'].queryset
    now = timezone.now()
    activities = visible_activities(request.user).filter(Q(host=request.user) | Q(group__in=groups)).filter(
        Q(status='cancelled') | Q(ends_at__lt=now) | Q(ends_at__isnull=True, starts_at__lt=now))
    query = request.GET.get('q', '').strip()
    if query:
        activities = activities.filter(Q(title__icontains=query) | Q(description__icontains=query))
    page = Paginator(activities.select_related('host__profile').order_by('-starts_at', '-pk'), 20).get_page(request.GET.get('page'))
    return render(request, 'activities/history.html', {'activities':page, 'query':query,
        'drafts': ActivityDraft.objects.filter(creator=request.user, published_at__isnull=True).order_by('-updated_at'),
        'suppress_create':True})


@login_required
@require_POST
def clone(request, pk):
    from .participation import locked_activity
    source_for(request.user, pk)
    with locked_activity(pk):
        source = source_for(request.user, pk)
        draft = ActivityDraft.objects.create(creator=request.user, source=source, source_title=source.title,
            values=copy_values(source, request.user), requires_schedule=bool(source.starts_at or source.participation_config and source.participation_config['pattern']=='scheduled'))
    return redirect('activities:draft', pk=draft.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    if request.method == 'POST':
        with transaction.atomic():
            # Write before read serializes SQLite and PostgreSQL publication/save.
            ActivityDraft.objects.filter(pk=pk, creator=request.user).update(revision=F('revision'))
            draft = get_object_or_404(ActivityDraft, pk=pk, creator=request.user)
            if draft.published_at:
                return published_redirect(draft)
            form = DraftForm(request.POST, draft=draft, user=request.user)
            action = request.POST.get('action')
            if action not in {'save', 'publish'}:
                raise Http404
            if form.is_valid() and (action == 'save' or form.validate_publication()):
                draft.values = form.copied_values()
                draft.revision += 1
                if action == 'publish':
                    activity = form.save(commit=False)
                    activity.host = request.user
                    activity.series = form.cleaned_data['series']
                    # ActivityForm's ordinary creation fallback uses today's Group
                    # artwork. Drafts instead honor their copied/explicit selection.
                    activity.header_image = form.cleaned_data['header_image']
                    activity.save()
                    from social.models import Interest
                    activity.interests.set(Interest.objects.filter(pk__in=draft.values.get('interests', [])))
                    publish_capabilities(activity, form.cleaned_data)
                    draft.published_activity = activity
                    draft.published_at = timezone.now()
                draft.save()
                messages.success(request, 'Activity published.' if draft.published_at else 'Draft saved; only you can see it.')
                return published_redirect(draft) if draft.published_at else redirect('activities:draft', pk=draft.pk)
    else:
        draft = get_object_or_404(ActivityDraft, pk=pk, creator=request.user)
        if draft.published_at:
            return published_redirect(draft)
        form = DraftForm(draft=draft, user=request.user)
    for section in form.sections:
        section['open'] = any(field.errors for field in section['fields'])
    return render(request, 'activities/draft.html', {'draft':draft, 'form':form, 'suppress_create':True})


def published_redirect(draft):
    if draft.published_activity_id:
        return redirect('activities:detail', pk=draft.published_activity_id)
    return redirect('activities:history')
