from __future__ import annotations

from django.http import Http404, HttpResponse
from django.utils.http import http_date
from django.views import View

from .models import ImageAsset


class ServeImageAssetView(View):
    http_method_names = ["get", "head"]

    def get(self, request, pk: str) -> HttpResponse:  # pragma: no cover - thin wrapper
        try:
            asset = ImageAsset.objects.only("data", "content_type", "size", "filename", "updated_at").get(pk=pk)
        except ImageAsset.DoesNotExist as exc:  # pragma: no cover
            raise Http404("Image not found") from exc

        response = HttpResponse(asset.data, content_type=asset.content_type)
        response["Content-Length"] = str(asset.size)
        response["Cache-Control"] = "public, max-age=86400"
        response["Last-Modified"] = http_date(asset.updated_at.timestamp())
        response["ETag"] = f'W/"{asset.updated_at.timestamp():.0f}-{asset.size}"'

        if asset.filename:
            response["Content-Disposition"] = f'inline; filename="{asset.filename}"'

        return response

    def head(self, request, pk: str) -> HttpResponse:  # pragma: no cover - HEAD response mirror
        return self.get(request, pk)
