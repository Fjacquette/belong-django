"""An invitation asks for RSVP; it never expands the Activity audience."""
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q, Value, IntegerField
from social.models import Friendship
from groups.models import GroupMembership, MemberStatus
from .models import ActivityInvitation

RSVP_LABELS = {'committed': "I'm coming", 'declined': "Can't make it"}


def with_invitation_state(queryset, user):
    return queryset.annotate(
        invitation_viewer_id=Value(user.pk, output_field=IntegerField()),
        direct_invited=Exists(ActivityInvitation.objects.filter(activity_id=OuterRef('pk'), user=user)),
        group_invited=Exists(GroupMembership.objects.filter(group_id=OuterRef('group_id'), user=user, status=MemberStatus.ACTIVE)),
    )


def is_invited(activity, user):
    if not user.is_authenticated:
        return False
    if getattr(activity, 'invitation_viewer_id', None) == user.pk:
        return activity.direct_invited or (activity.invite_group_members and activity.group_invited)
    return (activity.direct_invitations.filter(user=user).exists()
            or (activity.invite_group_members and activity.group_id
                and GroupMembership.objects.filter(group_id=activity.group_id, user=user, status=MemberStatus.ACTIVE).exists()))


def invitee_choices(activity, organizer):
    pairs = Friendship.objects.filter(Q(user_a=organizer) | Q(user_b=organizer)).values_list('user_a_id', 'user_b_id')
    ids = {pk for pair in pairs for pk in pair} - {organizer.pk}
    if activity.group_id:
        ids.update(GroupMembership.objects.filter(group_id=activity.group_id, status=MemberStatus.ACTIVE).values_list('user_id', flat=True))
    return get_user_model().objects.filter(pk__in=ids).exclude(pk=organizer.pk).select_related('profile').order_by('profile__display_name', 'username')


class InviteeField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return user.profile.identity_label


class DirectInviteForm(forms.Form):
    invitee = InviteeField(queryset=get_user_model().objects.none(), label='Invite a friend or active group member',
                          widget=forms.Select(attrs={'class': 'ui-field'}))

    def __init__(self, *args, activity, organizer, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invitee'].queryset = invitee_choices(activity, organizer)


class GroupInviteForm(forms.Form):
    invite_group_members = forms.BooleanField(required=False, label='Invite active group members', widget=forms.CheckboxInput(attrs={'class': 'ui-check'}))

    def __init__(self, *args, activity, **kwargs):
        self.activity = activity
        super().__init__(*args, **kwargs)

    def clean_invite_group_members(self):
        value = self.cleaned_data['invite_group_members']
        if value and not self.activity.group_id:
            raise forms.ValidationError('This occurrence has no associated Group.')
        return value


class EmailInviteForm(forms.Form):
    email = forms.EmailField(max_length=254, label='Email address',
                             widget=forms.EmailInput(attrs={'class': 'ui-field', 'autocomplete': 'email'}))
