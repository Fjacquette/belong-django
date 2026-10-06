from belong.test_helpers import create_legacy_user
from io import BytesIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .admin import ImageAssetAdmin
from .forms import ImageAssetAdminForm
from .models import ImageAsset, ImageAssetPurpose, ImageMetadata


def image_bytes(image_format="PNG"):
    output = BytesIO()
    Image.new("RGB", (4, 4), "red").save(output, format=image_format)
    return output.getvalue()


class ImageSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_legacy_user(username="image_viewer")

    def setUp(self):
        self.client.force_login(self.user)

    def upload_form(self, payload, filename="image.png", content_type="text/html", instance=None):
        return ImageAssetAdminForm(
            data={"name": "Uploaded image", "purpose": ImageAssetPurpose.ACTIVITY_HEADER},
            files={"upload": SimpleUploadedFile(filename, payload, content_type=content_type)},
            instance=instance,
        )

    def test_valid_image_upload_ignores_client_mime_and_filename(self):
        for image_format, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
            with self.subTest(image_format=image_format):
                payload = image_bytes(image_format)
                form = self.upload_form(payload, filename="spoofed.html")
                self.assertTrue(form.is_valid(), form.errors)
                asset = form.save()
                asset.refresh_from_db()
                self.assertEqual(asset.content_type, mime)
                self.assertEqual(bytes(asset.data), payload)
                self.assertEqual(asset.size, len(payload))
                response = self.client.get(asset.get_absolute_url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], mime)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.content, payload)

    def test_reported_gif_html_polyglot_and_invalid_images_are_rejected(self):
        payloads = (
            b"GIF89a<script>alert(document.cookie)</script>",
            b"<html><script>alert(document.cookie)</script></html>",
            b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
            b"\x89PNG\r\n\x1a\n<script>alert(1)</script>",
            image_bytes("PNG")[:30], image_bytes("GIF"), image_bytes("BMP"), b"",
        )
        for payload in payloads:
            with self.subTest(payload=payload[:20]):
                form = self.upload_form(payload, filename="evil.gif")
                self.assertFalse(form.is_valid())
        self.assertFalse(ImageAsset.objects.exists())

    def test_missing_image_is_rejected_for_new_uuid_instance(self):
        form = ImageAssetAdminForm(data={"name": "No file", "purpose": ImageAssetPurpose.GENERIC})
        self.assertFalse(form.is_valid())

    def test_existing_image_can_be_edited_without_reupload(self):
        form = self.upload_form(image_bytes())
        self.assertTrue(form.is_valid())
        asset = form.save()
        payload = bytes(asset.data)
        edited = ImageAssetAdminForm(
            data={"name": "New name", "purpose": ImageAssetPurpose.GENERIC}, instance=asset
        )
        self.assertTrue(edited.is_valid(), edited.errors)
        edited.save()
        asset.refresh_from_db()
        self.assertEqual(bytes(asset.data), payload)

    def test_oversized_decoded_images_and_animated_webp_are_rejected(self):
        with patch.object(Image, "MAX_IMAGE_PIXELS", 10):
            self.assertFalse(self.upload_form(image_bytes()).is_valid())
        output = BytesIO()
        Image.new("RGB", (4, 4), "red").save(
            output, format="WEBP", save_all=True,
            append_images=[Image.new("RGB", (4, 4), "blue")], duration=100, loop=0,
        )
        self.assertFalse(self.upload_form(output.getvalue()).is_valid())

    def test_legacy_stored_mime_and_size_are_not_trusted_for_get_or_head(self):
        payload = image_bytes() + b"<script>alert(document.cookie)</script>"
        asset = ImageAsset.objects.create(
            name="Legacy spoof", purpose=ImageAssetPurpose.GENERIC, data=payload,
            content_type="text/html", size=99999, filename='quoted"name.png',
        )
        for method in ("get", "head"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(asset.get_absolute_url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                self.assertEqual(response["Content-Length"], str(len(payload)))
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertIn('filename="quoted\\"name.png"', response["Content-Disposition"])
                self.assertEqual(response.content, payload if method == "get" else b"")
        asset.refresh_from_db()
        self.assertEqual(asset.content_type, "text/html")  # Reading does not rewrite user data.
        self.assertEqual(asset.size, 99999)

    def test_legacy_html_or_invalid_bytes_cannot_be_served(self):
        asset = ImageAsset.objects.create(
            name="Invalid legacy image", data=b"GIF89a<script>alert(1)</script>",
            content_type="text/html", size=30,
        )
        response = self.client.get(asset.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "<script>alert(1)</script>", status_code=404)
        preview = ImageAssetAdmin(ImageAsset, admin.site).preview(asset)
        self.assertEqual(preview, "Preview unavailable for this file type.")

    def test_images_require_authentication_including_head_and_unknown_ids(self):
        form = self.upload_form(image_bytes())
        self.assertTrue(form.is_valid())
        asset = form.save()
        self.client.logout()
        for method in ("get", "head"):
            for url in (asset.get_absolute_url(), reverse("media_assets:serve", args=["00000000-0000-0000-0000-000000000000"])):
                with self.subTest(method=method, url=url):
                    response = getattr(self.client, method)(url)
                    self.assertRedirects(response, f"{reverse('login')}?next={url}", fetch_redirect_response=False)
                    self.assertNotEqual(response["Content-Type"], "image/png")

    def test_from_upload_and_data_uri_derive_type_from_bytes(self):
        payload = image_bytes("JPEG")
        asset = ImageAsset.from_upload(
            name="Alternate API", purpose=ImageAssetPurpose.GENERIC, payload=payload,
            metadata=ImageMetadata(size=99999, content_type="text/html", filename="wrong.html"),
        )
        self.assertEqual(asset.content_type, "image/jpeg")
        self.assertEqual(asset.size, len(payload))
        asset.content_type = "text/html"
        self.assertTrue(asset.as_data_uri().startswith("data:image/jpeg;base64,"))
        with self.assertRaises(ValidationError):
            ImageAsset.from_upload(
                name="Invalid", purpose=ImageAssetPurpose.GENERIC, payload=b"<script>alert(1)</script>",
                metadata=ImageMetadata(size=25, content_type="image/jpeg"),
            )
