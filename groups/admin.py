from django.contrib import admin
from .models import Group, GroupMembership


class MembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    autocomplete_fields = ["user"]

    def has_delete_permission(self, request, obj=None):
        # Keep the primary organizer's roster entry intact in the inline.
        return False


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "access"]
    list_filter = ["access"]
    search_fields = ["name", "owner__username"]
    autocomplete_fields = ["owner"]
    inlines = [MembershipInline]

    def get_readonly_fields(self, request, obj=None):
        return ["owner"] if obj else []

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        GroupMembership.objects.update_or_create(group=form.instance, user=form.instance.owner, defaults={"role": "organizer", "status": "active"})
