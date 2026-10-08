from copy import deepcopy
from django import forms
from .participation_config import CREATOR_PATTERN_CHOICES, make_config, INTENT_VERSION, POLL_VERSION

from media_assets.models import ImageAsset, ImageAssetPurpose

from .models import (
    Activity,
    ActivitySeries,
    ActivityLocationType,
    ActivityResponseStatus,
    ActivityVisibility,
    DEFAULT_RESPONSE_CHOICES,
    PILOT_AUDIENCE_CHOICES,
    CURRENT_RESPONSE_CHOICES,
    current_response_values,
)

from .series import SERIES_DEFAULT_FIELDS

_DATETIME_INPUT_KWARGS = {
    "widget": forms.DateTimeInput(
        attrs={"type": "datetime-local"},
        format="%Y-%m-%dT%H:%M",
    ),
    "input_formats": ["%Y-%m-%dT%H:%M"],
    "required": False,
}


class ResponseChoicesWidget(forms.CheckboxSelectMultiple):
    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        option['attrs']['class'] = 'ui-check'
        return option


class ActivityDefaultsValidationMixin:
    def configure_participation_field(self):
        config = self.instance.participation_config or self.initial.get('participation_config')
        pattern = config['pattern'] if config else ''
        choices = list(CREATOR_PATTERN_CHOICES)
        if self._meta.model is Activity:
            choices.append(('planning', 'Tentative planning (three-date poll)'))
            for n in range(1, 4):
                self.fields[f'poll_date_{n}'] = forms.DateTimeField(**_DATETIME_INPUT_KWARGS, label=f'Poll date {n}',
                    help_text='For tentative planning only. Availability does not reserve a place.')
                self.fields[f'poll_date_{n}'].widget.attrs['class'] = 'ui-field mt-1'
        disabled = bool(self.instance.pk and pattern not in dict(choices))
        if disabled:
            choices.append((pattern, self.instance.participation_pattern_label))
        self.fields['participation_pattern'] = forms.ChoiceField(choices=choices, required=False,
            disabled=disabled, label='How will people take part?',
            help_text='Scheduled attendance, Join now and date polls require Free. Planning asks for availability before attendance. Invitees use the same pattern. External links never record attendance. Response choices apply only to the current flow.',
            widget=forms.Select(attrs={'class': 'ui-field mt-1'}))
        self.initial['participation_pattern'] = pattern
        self.stored_response_choices = deepcopy(self.instance.available_responses)
        first = ['group', 'participation_pattern'] + [f'poll_date_{n}' for n in range(1,4) if f'poll_date_{n}' in self.fields]
        self.order_fields(first + [name for name in self.fields if name not in first])

    def clean(self):
        data = super().clean()
        pattern = data.get('participation_pattern', '')
        if self.fields['participation_pattern'].disabled:
            config = self.instance.participation_config
        elif pattern:
            original = self.initial.get('participation_config') or self.instance.participation_config
            version = original['version'] if original and original['pattern'] == pattern else INTENT_VERSION if pattern in {'scheduled', 'immediate'} else POLL_VERSION if pattern == 'planning' else 1
            actions = deepcopy(original['actions']) if original and original['pattern'] == pattern else make_config(pattern, version=version)['actions']
            if 'open_external' not in actions and any(data.get(f'action{n}_url') for n in range(1, 4)):
                actions.append('open_external')
            config = make_config(pattern, actions=actions, version=version)
        else:
            config = None
        self.instance.participation_config = config
        if config is not None:
            # Retain authored legacy JSON on Series edits; configuration owns the
            # new behavior without pretending those choices are current actions.
            data['available_responses'] = self.stored_response_choices if self.instance.pk else []
        if config and config['version'] == POLL_VERSION and self._meta.model is Activity:
            from django.utils import timezone
            dates = [data.get(f'poll_date_{n}') for n in range(1,4)]
            for n, date in enumerate(dates, 1):
                if date is None or date <= timezone.now():
                    self.add_error(f'poll_date_{n}', 'Choose a future date and time.')
            if len(set(dates)) != 3:
                self.add_error('poll_date_1', 'Choose three different dates and times.')
            if data.get('starts_at') or data.get('ends_at'):
                self.add_error('starts_at', 'Leave the schedule undecided until you finalize a poll date.')
        if data.get('invite_group_members') and not data.get('group'):
            self.add_error('invite_group_members', 'Choose a Group to invite its members.')
        amount = data.get('cost_amount')
        kind = data.get('cost_type')
        if amount is not None:
            if kind == 'free' and amount != 0:
                self.add_error('cost_amount', 'A free activity must have a zero cost.')
            elif kind != 'free' and amount == 0:
                self.add_error('cost_type', 'Choose Free for a zero cost.')
            elif kind == 'unknown':
                self.add_error('cost_type', 'Choose Paid when the numeric cost is known.')
        return data

    def clean_location_gps(self):
        from .discovery import coordinates
        value = self.cleaned_data.get("location_gps", "").strip()
        if value and coordinates(value) is None:
            raise forms.ValidationError("Use latitude, longitude (for example 40.0, -75.0).")
        return value

    def clean_available_responses(self):
        responses = self.cleaned_data.get("available_responses") or []
        return list(responses)



class ActivityForm(ActivityDefaultsValidationMixin, forms.ModelForm):
    title = forms.CharField(max_length=48, help_text="Use Title Case, keeping names/acronyms like D&D or OW2 intact. Keep the activity name short (48 characters max). Put longer copy in the description.")
    location_name = forms.CharField(max_length=40, required=False, label="Venue / short location label",
                                   help_text="Use a short place name (40 characters max). Put the full address and directions below.")
    starts_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    ends_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    post_until = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    available_responses = forms.MultipleChoiceField(
        choices=CURRENT_RESPONSE_CHOICES,
        required=False,
        initial=list(DEFAULT_RESPONSE_CHOICES),
        widget=ResponseChoicesWidget,
        help_text="Choose what intent is useful for this activity. These choices apply only to Response choices (current flow). Scheduled, immediate and No response required use their own actions, including for invitees.",
    )

    class Meta:
        model = Activity
        fields = [
            "title",
            "group",
            "headline",
            "summary",
            "description",
            "category",
            "starts_at",
            "ends_at",
            "multiple_events",
            "freetext_when",
            "post_until",
            "location_type",
            "location_url",
            "location_name",
            "location_address1",
            "location_address2",
            "location_city",
            "location_state",
            "location_zip",
            "location_phone",
            "location_gps",
            "location_instructions",
            "organizer_name",
            "organizer_image",
            "audience",
            "allow_friend_invites",
            "allow_friend_of_friend_invites",
            "invite_group_members",
            "cost_type",
            "cost_amount",
            "cost_display",
            "cost_has_details",
            "accommodations",
            "restrictions",
            "header_image",
            "color_primary",
            "color_secondary",
            "action1_label",
            "action1_url",
            "action2_label",
            "action2_url",
            "action3_label",
            "action3_url",
            "available_responses",
            "capacity",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "summary": forms.Textarea(attrs={"rows": 3}),
            "accommodations": forms.Textarea(attrs={"rows": 2}),
            "restrictions": forms.Textarea(attrs={"rows": 2}),
            "audience": forms.Select(choices=PILOT_AUDIENCE_CHOICES),
            "location_type": forms.Select(choices=ActivityLocationType.choices),
        }

    def __init__(self, *args, user=None, context_group=None, context_series=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from groups.models import Group
        self.fields["group"].queryset = Group.objects.filter(
            Q(owner=user) | Q(memberships__user=user, memberships__role="organizer", memberships__status="active")
        ).distinct() if user and user.is_authenticated else Group.objects.none()
        self.fields['group'].label = 'For a group?'
        self.context_group = context_group
        self.fields['invite_group_members'].help_text = 'Invite active members of the associated Group; this does not change the activity audience.'
        self.context_series = context_series
        if context_group:
            self.initial.setdefault('invite_group_members', True)
            self.initial['group'] = context_group.pk
            self.fields['group'].disabled = True
            if not self.is_bound:
                self.initial.setdefault('header_image', context_group.default_activity_image_id)
        self.order_fields(['group'] + [name for name in self.fields if name != 'group'])
        self.fields["group"].help_text = "Optional. Link an activity to a group you organize; participation still follows the activity audience."
        self.fields["location_gps"].help_text = "Latitude, longitude; used for discovery distance tiers."
        self.fields["audience"].choices = PILOT_AUDIENCE_CHOICES
        for name in ("title", "location_name"):
            field_id = self[name].auto_id
            self.fields[name].widget.attrs["aria-describedby"] = f"{field_id}_helptext {field_id}_counter"
        base_classes = "ui-field mt-1"
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {base_classes}".strip()
            if isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs["class"] = "ui-choice-list"
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "ui-check"

        if self.instance and self.instance.pk and self.instance.available_responses:
            self.initial['available_responses'] = current_response_values(self.instance.available_responses) or list(DEFAULT_RESPONSE_CHOICES)
        if 'available_responses' in self.initial:
            self.initial['available_responses'] = current_response_values(self.initial['available_responses']) or list(DEFAULT_RESPONSE_CHOICES)
        self.fields["header_image"].queryset = ImageAsset.objects.filter(
            purpose=ImageAssetPurpose.ACTIVITY_HEADER
        )
        self.fields["organizer_image"].queryset = ImageAsset.objects.filter(
            purpose=ImageAssetPurpose.ORGANIZER
        )
        self.configure_participation_field()

    def save(self, commit=True):
        instance: Activity = super().save(commit=False)
        if not instance.pk and self.context_series:
            instance.series = self.context_series
            if not instance.header_image_id:
                instance.header_image = self.context_series.header_image
        if not instance.pk and not instance.header_image_id and instance.group_id:
            instance.header_image = instance.group.default_activity_image
        if instance.uses_legacy_participation and not instance.available_responses:
            instance.available_responses = list(DEFAULT_RESPONSE_CHOICES)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ActivitySeriesForm(ActivityDefaultsValidationMixin, forms.ModelForm):
    title = forms.CharField(max_length=48, help_text='A short name for this series, such as Weekend Hikes.')
    location_name = forms.CharField(max_length=40, required=False, label='Usual venue / short location label')
    available_responses = forms.MultipleChoiceField(choices=CURRENT_RESPONSE_CHOICES, required=False,
                                                   initial=list(DEFAULT_RESPONSE_CHOICES), widget=ResponseChoicesWidget,
                                                   help_text='Initial response choices for new occurrences.')

    class Meta:
        model = ActivitySeries
        fields = ['title', 'group', 'cadence', 'weekday', 'usual_start_time', 'cadence_description'] + [f for f in SERIES_DEFAULT_FIELDS if f not in {'title', 'participation_config'}]
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'location_instructions': forms.Textarea(attrs={'rows': 2}),
                   'usual_start_time': forms.TimeInput(attrs={'type': 'time'})}
        labels = {'group': 'For a group?', 'cadence': 'How often?', 'weekday': 'Usual day', 'usual_start_time': 'Usual start time', 'cadence_description': 'Schedule details'}

    def __init__(self, *args, user=None, context_group=None, **kwargs):
        super().__init__(*args, **kwargs)
        groups = ActivityForm(user=user).fields['group'].queryset
        self.fields['group'].queryset = groups
        self.fields['group'].help_text = 'Optional. Groups and activity audiences remain independent.'
        self.fields['header_image'].queryset = ImageAsset.objects.filter(purpose=ImageAssetPurpose.ACTIVITY_HEADER)
        self.fields['header_image'].help_text = 'Optional Series artwork; when blank, new occurrences use the group default.'
        if context_group:
            self.initial.setdefault('invite_group_members', True)
            self.initial['group'] = context_group.pk
            self.fields['group'].disabled = True
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'ui-choice-list' if isinstance(field.widget, forms.CheckboxSelectMultiple) else 'ui-check' if isinstance(field.widget, forms.CheckboxInput) else 'ui-field mt-1'
        if self.instance.pk:
            self.initial['available_responses'] = current_response_values(self.instance.available_responses) or list(DEFAULT_RESPONSE_CHOICES)
        self.configure_participation_field()

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.uses_legacy_participation and not instance.available_responses:
            instance.available_responses = list(DEFAULT_RESPONSE_CHOICES)
        if commit:
            instance.save()
        return instance


class CancelActivityForm(forms.Form):
    reason = forms.CharField(max_length=500, required=False, label='Cancellation reason (optional)',
                             widget=forms.Textarea(attrs={'class': 'ui-field', 'rows': 3}),
                             help_text='Visible to people who can view this activity. Cancels only this occurrence; responses are retained.')
