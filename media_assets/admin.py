from __future__ import annotations

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .forms import ImageAssetAdminForm
from .models import ImageAsset


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    form = ImageAssetAdminForm
    list_display = ("name", "purpose", "size_display", "updated_at")
    list_filter = ("purpose",)
    search_fields = ("name", "filename")
    ordering = ("name",)
    readonly_fields = ("preview", "size_display", "content_type", "filename", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "purpose", "upload")}),
        ("Current file", {"fields": ("preview", "size_display", "content_type", "filename")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def size_display(self, obj: ImageAsset) -> str:
        if not obj.pk or obj.size is None:
            return "—"
        return f"{obj.size / 1024:.1f} KB"

    size_display.short_description = "Size"

    def preview(self, obj: ImageAsset) -> str:
        if not obj.pk:
            return "Upload an image and save to see a preview."
        try:
            data_uri = obj.as_data_uri()
        except ValidationError:
            return "Preview unavailable for this file type."
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px;" alt="Preview">', data_uri)

    preview.short_description = "Preview"
