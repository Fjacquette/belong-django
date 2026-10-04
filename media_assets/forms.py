from __future__ import annotations

from django import forms

from .images import image_mime_type
from .models import ImageAsset


class ImageAssetAdminForm(forms.ModelForm):
    upload = forms.FileField(
        required=False,
        help_text="Upload a new image file to store in the database.",
    )

    class Meta:
        model = ImageAsset
        fields = ("name", "purpose", "upload")

    def clean(self):
        cleaned = super().clean()
        upload = cleaned.get("upload")

        if not upload and self.instance._state.adding:
            raise forms.ValidationError("Please upload an image to store.")

        if upload:
            if upload.size == 0:
                raise forms.ValidationError("Uploaded image is empty.")

            # We need the raw payload later, so read once and stash it.
            payload = upload.read()
            self._content_type = image_mime_type(payload)
            self._payload = payload

            # Leave the upload stream reusable; save() uses the validated payload.
            upload.seek(0)

        return cleaned

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        upload = self.cleaned_data.get("upload")

        if upload:
            payload = self._payload
            instance.data = payload
            instance.size = len(payload)
            instance.content_type = self._content_type
            instance.filename = upload.name

        if commit:
            instance.save()

        return instance
