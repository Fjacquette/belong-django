from django import forms

from media_assets.models import ImageAsset, ImageAssetPurpose

from .models import (
    Activity,
    ActivityLocationType,
    ActivityResponseStatus,
    ActivityVisibility,
    DEFAULT_RESPONSE_CHOICES,
    PILOT_AUDIENCE_CHOICES,
)

_DATETIME_INPUT_KWARGS = {
    "widget": forms.DateTimeInput(
        attrs={"type": "datetime-local"},
        format="%Y-%m-%dT%H:%M",
    ),
    "input_formats": ["%Y-%m-%dT%H:%M"],
    "required": False,
}


class ActivityForm(forms.ModelForm):
    title = forms.CharField(max_length=48, help_text="Use Title Case, keeping names/acronyms like D&D or OW2 intact. Keep the activity name short (48 characters max). Put longer copy in the description.")
    location_name = forms.CharField(max_length=40, required=False, label="Venue / short location label",
                                   help_text="Use a short place name (40 characters max). Put the full address and directions below.")
    starts_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    ends_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    post_until = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    available_responses = forms.MultipleChoiceField(
        choices=ActivityResponseStatus.choices,
        required=False,
        initial=list(DEFAULT_RESPONSE_CHOICES),
        widget=forms.CheckboxSelectMultiple,
        help_text="Choose what intent is useful for this activity. One or two complete choices appear on its card when they fit; all choices appear in Details.",
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
            "is_personal_invitation",
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
            "audience": forms.Select(choices=ActivityVisibility.choices),
            "location_type": forms.Select(choices=ActivityLocationType.choices),
        }

    def __init__(self, *args, user=None, context_group=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from groups.models import Group
        self.fields["group"].queryset = Group.objects.filter(
            Q(owner=user) | Q(memberships__user=user, memberships__role="organizer", memberships__status="active")
        ).distinct() if user and user.is_authenticated else Group.objects.none()
        self.fields['group'].label = 'For a group?'
        self.context_group = context_group
        if context_group:
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
                widget.attrs["class"] = "grid grid-cols-1 gap-2"
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "ui-check"

        if self.instance and self.instance.pk and self.instance.available_responses:
            self.fields["available_responses"].initial = self.instance.available_responses
        self.fields["header_image"].queryset = ImageAsset.objects.filter(
            purpose=ImageAssetPurpose.ACTIVITY_HEADER
        )
        self.fields["organizer_image"].queryset = ImageAsset.objects.filter(
            purpose=ImageAssetPurpose.ORGANIZER
        )

    def clean(self):
        data = super().clean()
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

    def save(self, commit=True):
        instance: Activity = super().save(commit=False)
        if not instance.pk and not instance.header_image_id and instance.group_id:
            instance.header_image = instance.group.default_activity_image
        if not instance.available_responses:
            instance.available_responses = list(DEFAULT_RESPONSE_CHOICES)
        if commit:
            instance.save()
            self.save_m2m()
        return instance
