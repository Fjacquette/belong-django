"""Validate actual image bytes; never trust filenames or multipart MIME headers."""

from io import BytesIO
import warnings

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

IMAGE_MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def image_mime_type(payload):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload), formats=list(IMAGE_MIME_TYPES)) as image:
                image_format = image.format
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported.")
                image.verify()
            # verify() alone does not decode the pixels. Reopen and load them too.
            with Image.open(BytesIO(payload), formats=list(IMAGE_MIME_TYPES)) as image:
                image.load()
        return IMAGE_MIME_TYPES[image_format]
    except (
        UnidentifiedImageError, OSError, ValueError, SyntaxError,
        Image.DecompressionBombError, Image.DecompressionBombWarning,
    ) as error:
        raise ValidationError("Upload a valid, non-animated JPEG, PNG, or WebP image.") from error
