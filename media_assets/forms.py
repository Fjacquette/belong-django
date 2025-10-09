from __future__ import annotations

import imghdr
import mimetypes

from django import forms

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

        if not upload and not self.instance.pk:
            raise forms.ValidationError("Please upload an image to store.")

        if upload:
            if upload.size == 0:
                raise forms.ValidationError("Uploaded image is empty.")

            # We need the raw payload later, so read once and stash it.
            payload = upload.read()
            image_type = imghdr.what(None, h=payload)
            if image_type is None:
                raise forms.ValidationError("Please upload a valid image file.")

            # Rewind so save() can read again.
            upload.seek(0)

        return cleaned

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        upload = self.cleaned_data.get("upload")

        if upload:
            payload = upload.read()
            upload.seek(0)
            content_type = upload.content_type or mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
            instance.data = payload
            instance.size = len(payload)
            instance.content_type = content_type
            instance.filename = upload.name

        if commit:
            instance.save()

        return instance
