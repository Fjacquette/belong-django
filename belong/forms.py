from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


BASE_INPUT_CLASSES = "ui-field min-h-11"


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {BASE_INPUT_CLASSES}".strip()
            if name == "username":
                field.widget.attrs.setdefault("placeholder", "Username")
            if name == "password":
                field.widget.attrs.setdefault("placeholder", "Password")


class StyledUserCreationForm(UserCreationForm):
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email. Sign in instead.')
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {BASE_INPUT_CLASSES}".strip()
            placeholders = {
                "username": "Choose a username",
                "password1": "Create a password",
                "password2": "Confirm password",
            }
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])
            field.help_text = None


class InvitedUserCreationForm(StyledUserCreationForm):
    def __init__(self, *args, invited_email, **kwargs):
        self.invited_email = invited_email
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['email'].initial = invited_email
        self.fields['email'].widget.attrs['readonly'] = True

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email != self.invited_email:
            raise forms.ValidationError('Use the invited email address.')
        return super().clean_email()
