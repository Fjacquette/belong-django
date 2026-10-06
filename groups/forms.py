from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "access"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {"access": "Group access"}
        help_texts = {"access": "Open: visible, join immediately. Closed: visible, request approval. Unlisted: join immediately through a link. Private: hidden, invitation only."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "ui-field mt-1"


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
