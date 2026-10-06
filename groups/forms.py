from django import forms

from .models import Group


ACCESS_COPY = {
    'open': 'Anyone can find the group, see what it’s about, and join immediately.',
    'closed': 'Anyone can find and view the group, but an organizer must approve new members.',
    'unlisted': 'The group won’t be promoted or listed publicly. Anyone with a direct link or arriving through an activity can view it and join immediately.',
    'private': 'Only members can see the group. New members join by invitation only.',
}


class GroupForm(forms.ModelForm):
    image_upload = forms.FileField(required=False, label='Upload group image', help_text='JPEG, PNG or WebP, up to 5 MB. Represents the group, not the human organizer.')
    default_activity_image_upload = forms.FileField(required=False, label='Upload default activity image', help_text='JPEG, PNG or WebP, up to 5 MB. New activities copy this artwork; organizers can override it.')

    class Meta:
        model = Group
        fields = ['name', 'description', 'access', 'image', 'image_upload', 'default_activity_image', 'default_activity_image_upload']
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'access': forms.RadioSelect}
        labels = {'access': 'Who can find and join this group?', 'image': 'Group image', 'default_activity_image': 'Default activity image'}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        from media_assets.models import ImageAsset, ImageAssetPurpose
        # Group identity artwork is selectable only from groups this user organizes.
        organized = Group.objects.filter(Q(owner=user) | Q(memberships__user=user, memberships__role='organizer', memberships__status='active')).distinct() if user else Group.objects.none()
        self.fields['image'].queryset = ImageAsset.objects.filter(purpose=ImageAssetPurpose.GROUP_IMAGE, group_images__in=organized).distinct()
        self.fields['default_activity_image'].queryset = ImageAsset.objects.filter(purpose=ImageAssetPurpose.ACTIVITY_HEADER)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'ui-check' if name == 'access' else 'ui-field mt-1'
        self.access_options = [{'radio': radio, 'description': ACCESS_COPY[radio.data['value']]} for radio in self['access']]

    def clean(self):
        cleaned = super().clean()
        from media_assets.images import image_mime_type
        for name in ['image_upload', 'default_activity_image_upload']:
            upload = cleaned.get(name)
            if upload:
                if upload.size > 5 * 1024 * 1024:
                    self.add_error(name, 'Upload an image of 5 MB or less.')
                    continue
                payload = upload.read()
                try:
                    mime = image_mime_type(payload)
                except forms.ValidationError as error:
                    self.add_error(name, error)
                else:
                    cleaned[name] = (upload.name, payload, mime)
        return cleaned

    def save(self, commit=True):
        from media_assets.models import ImageAsset, ImageAssetPurpose
        group = super().save(commit=False)
        for field, purpose in [('image', ImageAssetPurpose.GROUP_IMAGE), ('default_activity_image', ImageAssetPurpose.ACTIVITY_HEADER)]:
            upload = self.cleaned_data.get(field + '_upload')
            if upload:
                filename, payload, mime = upload
                asset = ImageAsset.objects.create(name=filename[:120], filename=filename[:255], purpose=purpose,
                                                  data=payload, size=len(payload), content_type=mime)
                setattr(group, field, asset)
        if commit:
            group.save()
        return group


class InvitationForm(forms.Form):
    emails = forms.CharField(label='Email addresses', max_length=4000,
                             help_text='Separate addresses with commas or new lines. Up to 20 at a time.',
                             widget=forms.Textarea(attrs={'rows': 3, 'class': 'ui-field mt-1'}))

    def clean_emails(self):
        import re
        from django.core.validators import validate_email
        emails = list(dict.fromkeys(e.strip().lower() for e in re.split(r'[,;\s]+', self.cleaned_data['emails']) if e.strip()))
        if not emails:
            raise forms.ValidationError('Enter at least one email address.')
        if len(emails) > 20:
            raise forms.ValidationError('Invite up to 20 addresses at a time.')
        for email in emails:
            validate_email(email)
        return emails
