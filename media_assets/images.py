"""Validate actual image bytes; never trust filenames or multipart MIME headers."""

from io import BytesIO
import warnings

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

IMAGE_MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def image_mime_type(payload, *, max_pixels=None):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload), formats=list(IMAGE_MIME_TYPES)) as image:
                if max_pixels is not None and image.width * image.height > max_pixels:
                    raise ValidationError('Choose an image with at most 25 million pixels.')
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


def normalized_avatar(upload):
    """Decode, orient, crop, and re-encode pixels without source metadata."""
    from PIL import ImageOps
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Choose an image smaller than 5 MB.')
    payload = upload.read()
    image_mime_type(payload, max_pixels=25_000_000)
    with Image.open(BytesIO(payload)) as source:
        pixels = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (256, 256), method=Image.Resampling.LANCZOS)
        pixels.info.clear()
        output = BytesIO()
        pixels.save(output, format='PNG')
    return output.getvalue()
