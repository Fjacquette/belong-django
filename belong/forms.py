
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from media_assets.images import normalized_avatar
from media_assets.models import ImageAsset, ImageAssetPurpose
from social.models import UserProfile, Interest, InterestSuggestion

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


class SignupEmailForm(forms.Form):
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    def __init__(self, *args, invited_email=None, **kwargs):
        self.invited_email = invited_email
        super().__init__(*args, **kwargs)
        if invited_email:
            self.fields['email'].initial = invited_email
            self.fields['email'].widget.attrs['readonly'] = True
        style_fields(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if self.invited_email and email != self.invited_email:
            raise forms.ValidationError('Use the invited email address.')
        return email


class AccountSetupForm(forms.Form):
    display_name = forms.CharField(max_length=120, label='Display name')
    account_type = forms.ChoiceField(choices=UserProfile._meta.get_field('account_type').choices,
                                    widget=forms.RadioSelect, label='Account type')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def __init__(self, *args, email, **kwargs):
        self.email = email
        super().__init__(*args, **kwargs)
        style_fields(self)

    def clean_password2(self):
        password = self.cleaned_data['password2']
        if password != self.cleaned_data.get('password1'):
            raise forms.ValidationError('The two passwords did not match.')
        validate_password(password, get_user_model()(email=self.email, first_name=self.cleaned_data.get('display_name', '')))
        return password


class RecoveryPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


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
