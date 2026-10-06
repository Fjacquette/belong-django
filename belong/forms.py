import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from media_assets.images import normalized_avatar
from media_assets.models import ImageAsset, ImageAssetPurpose
from social.models import UserProfile, Interest, InterestSuggestion
from .email_verification import email_available

BASE_INPUT_CLASSES = 'ui-field min-h-11'


def style_fields(form):
    for field in form.fields.values():
        if not isinstance(field.widget, (forms.RadioSelect, forms.CheckboxInput)):
            field.widget.attrs['class'] = BASE_INPUT_CLASSES


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Email', widget=forms.TextInput(attrs={'autocomplete': 'username', 'inputmode': 'email'}))
    error_messages = {**AuthenticationForm.error_messages, 'invalid_login': 'Please enter a correct email and password.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields['username'].widget.attrs['maxlength'] = 254


class StyledUserCreationForm(UserCreationForm):
    email = forms.EmailField(max_length=254)
    account_type = forms.ChoiceField(choices=UserProfile._meta.get_field('account_type').choices, widget=forms.RadioSelect, label='Account type')
    display_name = forms.CharField(max_length=120, label='Display name', help_text='The name people will see, or your organization’s name.')

    class Meta(UserCreationForm.Meta):
        fields = ('email',)

    field_order = ('email', 'password1', 'password2', 'account_type', 'display_name')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if not email_available(email):
            raise forms.ValidationError('An account already uses this email. Sign in instead.')
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields['password1'].help_text = 'Use at least 8 characters; avoid common passwords.'

    def save(self, commit=True):
        with transaction.atomic():
            self.instance.username = 'u_' + uuid.uuid4().hex
            user = super().save(commit=commit)
            if commit:
                profile = user.profile
                profile.account_type = self.cleaned_data['account_type']
                profile.display_name = self.cleaned_data['display_name']
                profile.legacy_access = False
                profile.interests_prompt_pending = True
                profile.save(update_fields=['account_type', 'display_name', 'legacy_access', 'interests_prompt_pending'])
            return user


class InvitedUserCreationForm(StyledUserCreationForm):
    def __init__(self, *args, invited_email, **kwargs):
        self.invited_email = invited_email
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = invited_email
        self.fields['email'].widget.attrs['readonly'] = True

    def clean_email(self):
        if self.cleaned_data['email'].strip().lower() != self.invited_email:
            raise forms.ValidationError('Use the invited email address.')
        return super().clean_email()


class ProfileForm(forms.ModelForm):
    avatar = forms.FileField(required=False, label='Profile image', help_text='Optional JPEG, PNG or WebP, up to 5 MB. Saved as a square icon.')
    remove_avatar = forms.BooleanField(required=False, label='Remove current profile image')

    class Meta:
        model = UserProfile
        fields = ('display_name', 'account_type', 'location')
        widgets = {'account_type': forms.RadioSelect}
        labels = {'location': 'Home area (optional)'}
        help_texts = {'location': 'A locality or postal code, not your street address.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields['avatar'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'

    def clean_avatar(self):
        upload = self.cleaned_data['avatar']
        return normalized_avatar(upload) if upload else None

    def save(self, commit=True):
        with transaction.atomic():
            profile = super().save(commit=False)
            payload = self.cleaned_data.get('avatar')
            if payload:
                profile.avatar_image = ImageAsset.objects.create(name=f'Profile {profile.user_id}', purpose=ImageAssetPurpose.PROFILE_AVATAR, data=payload, content_type='image/png', size=len(payload), filename='profile.png')
            elif self.cleaned_data.get('remove_avatar'):
                profile.avatar_image = None
            if commit:
                profile.save()
            return profile


class EmailChangeForm(forms.Form):
    email = forms.EmailField(max_length=254, label='New email address')
    current_password = forms.CharField(widget=forms.PasswordInput, label='Current password')

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email == self.user.email.lower():
            raise forms.ValidationError('This is already your current email address.')
        if not email_available(email, self.user):
            raise forms.ValidationError('An account already uses this email. Sign in instead.')
        return email

    def clean_current_password(self):
        password = self.cleaned_data['current_password']
        if not self.user.check_password(password):
            raise forms.ValidationError('Enter your current password.')
        return password


class VerificationEmailForm(forms.Form):
    email = forms.EmailField(max_length=254, label='Email address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class InterestsForm(forms.Form):
    interests = forms.ModelMultipleChoiceField(queryset=Interest.objects.all(), required=False,
                                               widget=forms.CheckboxSelectMultiple)
    suggestion = forms.CharField(label='Something else?', max_length=300, required=False,
        help_text='Suggest an interest for us to consider. Suggestions are private and do not become matching tags.',
        widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASSES}))

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        kwargs.setdefault('initial', {'interests': profile.interests.all()})
        super().__init__(*args, **kwargs)

    def clean_interests(self):
        interests = self.cleaned_data['interests']
        if len(interests) > 20:
            raise forms.ValidationError('Choose up to 20 interests.')
        return interests

    def save(self):
        with transaction.atomic():
            self.profile.interests.set(self.cleaned_data['interests'])
            if self.cleaned_data['suggestion']:
                InterestSuggestion.objects.create(profile=self.profile, text=self.cleaned_data['suggestion'])
            self.profile.interests_prompt_pending = False
            self.profile.save(update_fields=['interests_prompt_pending'])
