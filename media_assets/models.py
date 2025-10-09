from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass

from django.db import models
from django.urls import reverse


class ImageAssetPurpose(models.TextChoices):
    GENERIC = "generic", "Generic"
    PROFILE_AVATAR = "profile_avatar", "Profile avatar"
    ORGANIZER = "organizer", "Activity organizer"
    ACTIVITY_HEADER = "activity_header", "Activity header"


@dataclass
class ImageMetadata:
    size: int
    content_type: str
    filename: str | None = None


class ImageAsset(models.Model):
    """
    Binary image storage used for profile avatars and activity artwork.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    purpose = models.CharField(
        max_length=40,
        choices=ImageAssetPurpose.choices,
        default=ImageAssetPurpose.GENERIC,
        help_text="Used to filter image choices in forms.",
    )
    data = models.BinaryField()
    content_type = models.CharField(max_length=120)
    size = models.PositiveIntegerField()
    filename = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    def as_data_uri(self) -> str:
        """
        Return a data: URI representation of the stored image.
        Useful for quickly linking to binary assets without generating a new request.
        """
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.content_type};base64,{encoded}"

    def get_absolute_url(self) -> str:
        return reverse("media_assets:serve", args=[str(self.id)])

    @classmethod
    def from_upload(cls, *, name: str, purpose: str, payload: bytes, metadata: ImageMetadata) -> "ImageAsset":
        return cls(
            name=name,
            purpose=purpose,
            data=payload,
            content_type=metadata.content_type,
            size=metadata.size,
            filename=metadata.filename or "",
        )
