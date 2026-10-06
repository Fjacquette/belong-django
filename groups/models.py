from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class GroupAccess(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"
    UNLISTED = "unlisted", "Unlisted"
    PRIVATE = "private", "Private"


class MemberRole(models.TextChoices):
    MEMBER = "member", "Member"
    ORGANIZER = "organizer", "Organizer"


class MemberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PENDING = "pending", "Awaiting approval"
    BLOCKED = "blocked", "Blocked"


class Group(models.Model):
    interests = models.ManyToManyField("social.Interest", blank=True, related_name="groups")
    image = models.ForeignKey("media_assets.ImageAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="group_images", limit_choices_to={"purpose": "group_image"})
    default_activity_image = models.ForeignKey("media_assets.ImageAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="default_activity_groups", limit_choices_to={"purpose": "activity_header"})
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_groups")
    access = models.CharField(max_length=12, choices=GroupAccess.choices, default=GroupAccess.CLOSED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(access__in=GroupAccess.values), name="group_valid_access"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("groups:detail", args=[self.pk])

    def membership_for(self, user):
        if not user.is_authenticated:
            return None
        return self.memberships.filter(user=user).first()

    def can_view(self, user):
        if not user.is_authenticated:
            return False
        return self.access != GroupAccess.PRIVATE or self.owner_id == user.pk or self.memberships.filter(user=user, status=MemberStatus.ACTIVE).exists()

    @property
    def access_description(self):
        return {
            GroupAccess.OPEN: "Visible; anyone can join immediately unless blocked.",
            GroupAccess.CLOSED: "Visible; membership requires organizer approval.",
            GroupAccess.UNLISTED: "Reachable through a link or linked activity; anyone can join immediately unless blocked.",
            GroupAccess.PRIVATE: "Hidden from nonmembers; membership requires an invitation.",
        }[self.access]

    def can_organize(self, user):
        return user.is_authenticated and (self.owner_id == user.pk or self.memberships.filter(user=user, status=MemberStatus.ACTIVE, role=MemberRole.ORGANIZER).exists())


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=12, choices=MemberRole.choices, default=MemberRole.MEMBER)
    status = models.CharField(max_length=12, choices=MemberStatus.choices, default=MemberStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_group_member"),
            models.CheckConstraint(condition=models.Q(role__in=MemberRole.values), name="group_member_valid_role"),
            models.CheckConstraint(condition=models.Q(status__in=MemberStatus.values), name="group_member_valid_status"),
            models.CheckConstraint(condition=~models.Q(role=MemberRole.ORGANIZER) | models.Q(status=MemberStatus.ACTIVE), name="group_organizer_active"),
        ]

    def clean(self):
        super().clean()
        if self.group_id and self.user_id == self.group.owner_id and (self.role != MemberRole.ORGANIZER or self.status != MemberStatus.ACTIVE):
            raise ValidationError("The primary organizer must remain an active organizer.")

    def __str__(self):
        return f"{self.user} in {self.group}"


class GroupInvitation(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_group_invitations')
    token_digest = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=12, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('revoked', 'Revoked')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_group_invitations')

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['group', 'email'], name='unique_group_invitation_email'),
            models.CheckConstraint(condition=models.Q(status__in=['pending', 'accepted', 'revoked']), name='group_invitation_valid_status'),
        ]

    @property
    def display_status(self):
        from django.utils import timezone
        if self.status == 'pending' and self.expires_at <= timezone.now():
            return 'Expired'
        return self.get_status_display()
