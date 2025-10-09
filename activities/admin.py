from django.contrib import admin

from .models import Activity, ActivityCategory, ActivityResponse


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tagline")
    search_fields = ("name", "tagline")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "host",
        "category",
        "audience",
        "starts_at",
        "multiple_events",
    )
    list_filter = ("audience", "category", "multiple_events", "starts_at")
    search_fields = ("title", "headline", "description", "summary")
    ordering = ("-starts_at", "-created_at")
    autocomplete_fields = ("host", "category", "organizer_image", "header_image")


@admin.register(ActivityResponse)
class ActivityResponseAdmin(admin.ModelAdmin):
    list_display = ("activity", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("activity__title", "user__username")
    autocomplete_fields = ("activity", "user")
