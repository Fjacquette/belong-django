from django.contrib import admin

from .models import FriendGroup, FriendGroupMembership, FriendRequest, Friendship, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status_text", "is_visible", "last_active_at")
    search_fields = ("user__username", "status_text")
    list_filter = ("is_visible",)


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "status", "created_at", "responded_at")
    list_filter = ("status", "created_at")
    search_fields = ("sender__username", "recipient__username")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("user_a", "user_b", "created_at")
    search_fields = ("user_a__username", "user_b__username")


class FriendGroupMembershipInline(admin.TabularInline):
    model = FriendGroupMembership
    extra = 1


@admin.register(FriendGroup)
class FriendGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")
    inlines = [FriendGroupMembershipInline]
