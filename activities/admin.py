from django.contrib import admin

from .models import Activity, ActivityCategory, ActivityResponse, PILOT_AUDIENCE_CHOICES


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tagline")
    search_fields = ("name", "tagline")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "audience":
            kwargs["choices"] = PILOT_AUDIENCE_CHOICES
        return super().formfield_for_choice_field(db_field, request, **kwargs)

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
    autocomplete_fields = ("host", "category", "group", "organizer_image", "header_image")


@admin.register(ActivityResponse)
class ActivityResponseAdmin(admin.ModelAdmin):
    list_display = ("activity", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("activity__title", "user__username")
    autocomplete_fields = ("activity", "user")
