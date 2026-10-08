"""Date poll → immutable decision → independent attendance round.

All writes use the existing occurrence lock. No poll answer writes ActivityResponse.
"""
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .models import (Activity, DatePoll, DatePollOption, DatePollSubmission,
                     ConfirmationRound, ConfirmationInvitation, AttendanceAnswer)
from .participation import locked_activity
from .visibility import visible_activities

AVAILABILITY = [('yes', 'Yes'), ('maybe', 'Maybe'), ('no', 'No')]


def poll_for(activity):
    if not activity.is_date_planning:
        return None
    try:
        return activity.date_poll
    except DatePoll.DoesNotExist:
        return None


def confirmation_for(activity):
    poll = poll_for(activity)
    if poll:
        try:
            return poll.confirmation
        except ConfirmationRound.DoesNotExist:
            pass
    return None


def latest_rows(rows):
    latest = {}
    for row in rows.order_by('pk'):
        latest[row.user_id] = row
    return list(latest.values())


def responses_for(activity):
    if not activity.is_date_planning:
        return list(activity.responses.all())
    round = confirmation_for(activity)
    return [r for r in latest_rows(round.answers.select_related('user__profile')) if r.status != 'withdrawn'] if round else []


def has_response(activity, user, *, affirmative=False):
    return any(r.user_id == user.pk and (not affirmative or r.status == 'committed') for r in responses_for(activity))


def recipient_ids(activity):
    if not activity.is_date_planning:
        return set(activity.responses.exclude(status='declined').values_list('user_id', flat=True))
    return {r.user_id for r in responses_for(activity) if r.status == 'committed'}


class PollAnswerForm(forms.Form):
    def __init__(self, *args, poll, **kwargs):
        super().__init__(*args, **kwargs)
        for option in poll.options.all():
            self.fields[f'option_{option.pk}'] = forms.ChoiceField(choices=AVAILABILITY,
                label=date_format(timezone.localtime(option.starts_at), 'D M j, Y, g:i A'),
                widget=forms.RadioSelect(attrs={'class':'ui-check'}))

    def answers(self):
        return {name.removeprefix('option_'):value for name,value in self.cleaned_data.items()}


def create_poll(activity, dates):
    poll = DatePoll.objects.create(activity=activity)
    DatePollOption.objects.bulk_create([DatePollOption(poll=poll,position=n,starts_at=date) for n,date in enumerate(dates,1)])
    return poll


def submit_answers(pk, user, data):
    with locked_activity(pk) as activity:
        if not visible_activities(user).filter(pk=pk).exists():
            raise Http404
        poll = poll_for(activity)
        if not poll:
            raise Http404
        if activity.is_cancelled or confirmation_for(activity):
            return 'This poll is closed. Your answers are retained.'
        form = PollAnswerForm(data, poll=poll)
        if not form.is_valid():
            return 'Choose Yes, Maybe or No for each date.'
        answers = form.answers()
        old = poll.submissions.filter(user=user).last()
        if not old or old.answers != answers:
            DatePollSubmission.objects.create(poll=poll,user=user,answers=answers)
        return 'Availability saved. You have not confirmed attendance or reserved a place.'


def finalize_poll(pk, organizer, option_id):
    with locked_activity(pk) as activity:
        if not activity.can_organize(organizer):
            raise Http404
        poll = poll_for(activity)
        if not poll:
            raise Http404
        if activity.is_cancelled:
            return 'This activity is cancelled; the poll cannot be finalized.'
        existing = confirmation_for(activity)
        if existing:
            return 'The selected date is already finalized; confirmation invitations are retained.'
        # Existing secured places need a reviewed reconfirmation policy, not a
        # release, overwrite or invented entitlement for a different date.
        if activity.responses.filter(status='committed').exists():
            return 'Existing secured places need review before this poll can be finalized. No responses or places changed.'
        activity.validate_participation_policy()
        option = get_object_or_404(poll.options,pk=option_id)
        if option.starts_at <= timezone.now():
            return 'Choose a future poll date; the selected date has passed.'
        round = ConfirmationRound.objects.create(poll=poll,selected_option=option,finalized_by=organizer,
            prior_schedule={'starts_at':activity.starts_at.isoformat() if activity.starts_at else None,
                'ends_at':activity.ends_at.isoformat() if activity.ends_at else None,'freetext_when':activity.freetext_when})
        activity.starts_at=option.starts_at
        activity.ends_at=None
        activity.save(update_fields=['starts_at','ends_at','updated_at'])
        participants = set(poll.submissions.values_list('user_id',flat=True))
        ConfirmationInvitation.objects.bulk_create([ConfirmationInvitation(round=round,user_id=pk) for pk in sorted(participants)])
        from .notifications import queue_event
        queue_event(activity,organizer,'confirmation',confirmation_round=round)
        return 'Date finalized. Every poll participant is invited to confirm attendance; no one is automatically Going.'


def change_attendance_locked(activity, user, action, round_id, *, toggle=False, remove=False, join=False):
    round = confirmation_for(activity)
    if not round or str(round.pk) != str(round_id):
        return 'Use the current confirmation invitation to answer this selected date.'
    if activity.is_cancelled:
        return 'This activity is cancelled. Attendance and poll history are retained.'
    activity.validate_participation_policy()
    meanings = {'confirm_attendance':'committed','decline_attendance':'declined'}
    if not remove and not join and action not in meanings:
        return 'Choose an available attendance action.'
    current = round.answers.filter(user=user).last()
    status = 'withdrawn' if remove else 'committed' if join else meanings[action]
    if toggle and current and current.status == status:
        status = 'withdrawn'
    if (not current and status == 'withdrawn') or (current and current.status == status):
        return ''
    if status == 'committed':
        count = sum(r.status == 'committed' for r in responses_for(activity))
        if activity.capacity is not None and count >= activity.capacity:
            return 'This activity is full. Your response has not changed.'
    AttendanceAnswer.objects.create(round=round,user=user,status=status)
    if status != 'withdrawn':
        from .group_offers import offer_after_response
        offer_after_response(activity,user)
    return ''


def poll_context(request, activity, *, organizer=False):
    poll = poll_for(activity)
    if not poll:
        return {}
    options = list(poll.options.all())
    submissions = latest_rows(poll.submissions.select_related('user__profile'))
    own = next((s for s in submissions if s.user_id == request.user.pk), None)
    round = confirmation_for(activity)
    selected = round.selected_option_id if round else None
    rows = [{'option':o,'selected':o.pk == selected,'own_answer':dict(AVAILABILITY).get(own.answers.get(str(o.pk)), '') if own else '',
             'counts':[(label,sum(s.answers.get(str(o.pk)) == value for s in submissions)) for value,label in AVAILABILITY]} for o in options]
    form = PollAnswerForm(poll=poll,initial={f'option_{pk}':value for pk,value in own.answers.items()} if own else {})
    if request.method == 'POST' and request.resolver_match and request.resolver_match.url_name == 'poll_vote' and not round and not activity.is_cancelled:
        form=PollAnswerForm(request.POST,poll=poll);form.is_valid()
    histories = poll.submissions.select_related('user__profile') if organizer else poll.submissions.filter(user=request.user)
    history = [{'user':s.user,'created_at':s.created_at,'answers':[(o.starts_at,dict(AVAILABILITY).get(s.answers.get(str(o.pk)),'')) for o in options]} for s in histories]
    return {'date_poll':poll,'poll_rows':rows,'poll_form':form,'poll_answered':own is not None,
            'poll_history':history,'poll_participant_count':len(submissions),'confirmation_round':round,
            'poll_closed':bool(round or activity.is_cancelled),
            'prior_responses':activity.responses.select_related('user__profile') if organizer else activity.responses.filter(user=request.user),
            'attendance_history':list(round.answers.select_related('user__profile')) if round and organizer else [],
            'confirmation_invitation_count':round.invitations.count() if round and organizer else 0}


@login_required
@require_POST
def vote(request, pk):
    notice=submit_answers(pk,request.user,request.POST)
    activity=get_object_or_404(visible_activities(request.user),pk=pk)
    from .views import _render_join_region
    return _render_join_region(request,activity,notice)


@login_required
@require_POST
def finalize(request, pk):
    option=request.POST.get('option','')
    if not option.isdigit():
        raise Http404
    notice=finalize_poll(pk,request.user,int(option))
    messages.info(request,notice)
    return redirect(reverse('activities:roster',args=[pk]))
