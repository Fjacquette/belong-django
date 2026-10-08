"""Optional Group admission after an independently recorded Activity response."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, F, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from groups.models import Group, GroupAccess, GroupMembership, MemberStatus
from groups.membership import join_group
from .models import GroupJoinOffer
from .participation import locked_activity
from .visibility import visible_activities
from .polls import has_response


def eligible(group, user):
    return bool(group and user.is_authenticated and user.is_active
                and group.access in [GroupAccess.OPEN, GroupAccess.CLOSED, GroupAccess.UNLISTED]
                and group.owner_id != user.pk and group.can_view(user)
                and not group.memberships.filter(user=user).exists())


def offer_after_response(activity, user):
    # Called only after successful response creation/update, in its writer transaction.
    if not eligible(activity.group, user):
        return
    offer, created = GroupJoinOffer.objects.get_or_create(user=user, group=activity.group,
                                                         defaults={'activity': activity})
    if not created and offer.status == 'pending' and offer.activity_id != activity.pk:
        offer.activity = activity
        offer.save(update_fields=['activity'])


def current_offer(user, activity=None):
    membership = GroupMembership.objects.filter(group_id=OuterRef('group_id'), user=user)
    # Compare the current occurrence association to the recorded Group; edits cannot
    # silently turn consent for one Group into consent for a different Group.
    offers = GroupJoinOffer.objects.filter(user=user, status='pending',
        group__access__in=[GroupAccess.OPEN, GroupAccess.CLOSED, GroupAccess.UNLISTED],
        activity__in=visible_activities(user), activity__group_id=F('group_id'))
    offers = offers.exclude(group__owner=user).annotate(has_membership=Exists(membership)).filter(has_membership=False)
    if activity is not None:
        offers = offers.filter(activity=activity)
    return next((offer for offer in offers.select_related('group', 'activity').order_by('-created_at', '-pk')
                 if has_response(offer.activity,user)),None)


@login_required
@require_POST
def answer(request, pk):
    action = request.POST.get('action')
    if action not in ['join', 'dismiss']:
        raise Http404
    get_object_or_404(visible_activities(request.user), pk=pk)
    with locked_activity(pk) as activity:
        if not visible_activities(request.user).filter(pk=activity.pk).exists():
            raise Http404
        reference = get_object_or_404(GroupJoinOffer, user=request.user, activity=activity)
        # Normal Group admission locks Group before resolving its offer. Keep the
        # same order here, then re-read the offer under lock for concurrent answers.
        group = get_object_or_404(Group.objects.select_for_update(), pk=reference.group_id)
        offer = get_object_or_404(GroupJoinOffer.objects.select_for_update(),
                                  user=request.user, activity=activity, group=group)
        if not has_response(activity,request.user):
            raise Http404
        result = 'Group invitation dismissed. Your activity response is unchanged.'
        result_group = None
        if offer.status == 'pending':
            if action == 'dismiss':
                offer.status = 'dismissed'
            else:
                if activity.group_id != group.pk or not eligible(group, request.user):
                    raise Http404
                membership = join_group(group.pk, request.user)
                offer.status = 'accepted'
                result = ('Your request is awaiting organizer approval.' if membership.status == MemberStatus.PENDING
                          else 'You joined the Group.') + ' Your activity response is unchanged.'
                result_group = group
            offer.save(update_fields=['status'])
        else:
            result = 'This Group invitation has already been handled. Your activity response is unchanged.'
        from .views import _participation_next_path
        destination = _participation_next_path(request, activity)
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'activities/_group_join_offer.html', {
            'group_join_result': result, 'result_group': result_group,
        })
    messages.success(request, result)
    return redirect(destination)
