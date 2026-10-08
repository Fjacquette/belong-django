from django.contrib import admin
from django import forms

from .models import Activity, ActivitySeries, ActivityCategory, ActivityResponse, PILOT_AUDIENCE_CHOICES, CURRENT_RESPONSE_CHOICES, ActivityResponseStatus, ActivityNotificationEvent, ActivityNotificationDelivery


class ActivityResponseAdminForm(forms.ModelForm):
    class Meta:
        model = ActivityResponse
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = list(CURRENT_RESPONSE_CHOICES)
        if self.instance.pk and self.instance.status == ActivityResponseStatus.INTERESTED:
            self.fields['status'].choices.append((ActivityResponseStatus.INTERESTED, ActivityResponseStatus.INTERESTED.label))

    def clean(self):
        data = super().clean()
        activity = data.get('activity')
        if activity and not activity.uses_legacy_participation and (
            not self.instance.pk or activity.pk != self.instance.activity_id
            or data.get('user') != self.instance.user or data.get('status') != self.instance.status
        ):
            raise forms.ValidationError('This activity does not accept response changes.')
        return data


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tagline")
    search_fields = ("name", "tagline")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    readonly_fields = ('status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'participation_config')
    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "audience":
            kwargs["choices"] = PILOT_AUDIENCE_CHOICES
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    list_display = (
        "title",
        "host",
        "status",
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
    form = ActivityResponseAdminForm
    list_display = ("activity", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("activity__title", "user__username")
    autocomplete_fields = ("activity", "user")


@admin.register(ActivitySeries)
class ActivitySeriesAdmin(admin.ModelAdmin):
    readonly_fields = ('participation_config',)
    list_display = ('title', 'owner', 'group', 'cadence')
    search_fields = ('title', 'description')
    autocomplete_fields = ('owner', 'group', 'category', 'header_image')


class NotificationAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityNotificationEvent)
class NotificationEventAdmin(NotificationAuditAdmin):
    list_display = ('id', 'activity', 'kind', 'actor', 'created_at')
    list_filter = ('kind',)


@admin.register(ActivityNotificationDelivery)
class NotificationDeliveryAdmin(NotificationAuditAdmin):
    list_display = ('id', 'event', 'recipient', 'status', 'reason', 'attempts', 'retry_at', 'attempt')
    list_filter = ('status', 'channel', 'event__kind')
