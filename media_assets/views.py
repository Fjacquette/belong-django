from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.utils.http import content_disposition_header, http_date
from django.views import View

from .models import ImageAsset
from .images import image_mime_type


class ServeImageAssetView(LoginRequiredMixin, View):
    http_method_names = ["get", "head"]

    def get(self, request, pk: str) -> HttpResponse:  # pragma: no cover - thin wrapper
        try:
            asset = ImageAsset.objects.only("data", "content_type", "size", "filename", "updated_at").get(pk=pk)
        except ImageAsset.DoesNotExist as exc:  # pragma: no cover
            raise Http404("Image not found") from exc

        payload = bytes(asset.data)
        try:
            content_type = image_mime_type(payload)
        except ValidationError as exc:
            raise Http404("Image not found") from exc
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Length"] = str(len(payload))
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Last-Modified"] = http_date(asset.updated_at.timestamp())
        response["ETag"] = f'W/"{asset.updated_at.timestamp():.0f}-{len(payload)}"'

        if asset.filename:
            response["Content-Disposition"] = content_disposition_header(False, asset.filename)

        return response

    def head(self, request, pk: str) -> HttpResponse:  # pragma: no cover - HEAD response mirror
        return self.get(request, pk)
