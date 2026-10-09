from django.contrib import admin

from .models import FriendGroup, FriendGroupMembership, FriendRequest, Friendship, UserProfile, Interest, InterestSuggestion, OutboundEmailAttempt


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status_text", "is_visible", "last_active_at", "outbound_mail_suspended")
    search_fields = ("user__username", "status_text")
    list_filter = ("is_visible", "outbound_mail_suspended")
    autocomplete_fields = ("user", "avatar_image")


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


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'section')
    search_fields = ('name', 'slug', 'section')
    list_filter = ('section',)


@admin.register(InterestSuggestion)
class InterestSuggestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'profile', 'created_at')
    search_fields = ('text',)
    readonly_fields = ('profile', 'text', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(OutboundEmailAttempt)
class OutboundEmailAttemptAdmin(admin.ModelAdmin):
    list_display = ('kind', 'actor', 'recipient_hash', 'created_at', 'outcome', 'reason')
    list_filter = ('kind', 'outcome', 'reason')
    search_fields = ('recipient_hash', 'actor__username')
    readonly_fields = ('kind', 'actor', 'recipient_hash', 'ip_hash', 'group_reference', 'activity_reference', 'created_at', 'outcome', 'reason')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from django.shortcuts import render
from .models import BetaAdmission


@admin.register(BetaAdmission)
class BetaAdmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'email', 'issued_by', 'issued_at', 'expires_at', 'redeemed_at', 'revoked_at')
    list_filter = ('kind', 'redeemed_at', 'revoked_at')
    search_fields = ('email',)
    exclude = ('verifier', 'source_digest')
    actions = ('revoke_selected',)

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields
            if field.name not in {'verifier', 'source_digest'} and (obj or field.name != 'email'))

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        from belong.beta_admission import issue_code
        admission, token = issue_code(obj.email, request.user)
        obj.__dict__.update(admission.__dict__)
        obj._issued_token = token  # Response only: never sessions, messages or admin logs.

    def response_add(self, request, obj, post_url_continue=None):
        response = render(request, 'admin/social/betaadmission/issued.html', {
            **self.admin_site.each_context(request), 'title':'Beta invitation created', 'code':obj._issued_token,
            'admission':obj, 'opts':self.model._meta})
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response

    @admin.action(description='Revoke selected unused beta admissions')
    def revoke_selected(self, request, queryset):
        from belong.beta_admission import revoke
        count = revoke(queryset, request.user)
        for obj in queryset:
            self.log_change(request, obj, 'Revoked beta admission')
        self.message_user(request, f'Revoked {count} unused beta admissions.')
