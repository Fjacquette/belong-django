from django import forms

from .models import (
    Activity,
    ActivityLocationType,
    ActivityResponseStatus,
    ActivityVisibility,
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
    starts_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    ends_at = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    post_until = forms.DateTimeField(**_DATETIME_INPUT_KWARGS)
    available_responses = forms.MultipleChoiceField(
        choices=ActivityResponseStatus.choices,
        required=False,
        initial=[choice[0] for choice in ActivityResponseStatus.choices],
        widget=forms.CheckboxSelectMultiple,
        help_text="Choose the response options attendees can pick from.",
    )

    class Meta:
        model = Activity
        fields = [
            "title",
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
            "audience",
            "allow_friend_invites",
            "allow_friend_of_friend_invites",
            "is_personal_invitation",
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        base_classes = (
            "mt-1 w-full border border-white/70 rounded-xl px-4 py-2 bg-white "
            "focus:outline-none focus:ring-2 focus:ring-belong-purple/30 focus:border-belong-purple"
        )
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {base_classes}".strip()
            if isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs["class"] = "grid grid-cols-1 gap-2"

        if self.instance and self.instance.pk and self.instance.available_responses:
            self.fields["available_responses"].initial = self.instance.available_responses

    def clean_available_responses(self):
        responses = self.cleaned_data.get("available_responses") or []
        return list(responses)

    def save(self, commit=True):
        instance: Activity = super().save(commit=False)
        if not instance.available_responses:
            instance.available_responses = [choice[0] for choice in ActivityResponseStatus.choices]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
