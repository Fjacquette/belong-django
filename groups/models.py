from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class GroupVisibility(models.TextChoices):
    PUBLIC = "public", "Public — visible through linked activities"
    UNLISTED = "unlisted", "Unlisted — accessible by direct link"
    PRIVATE = "private", "Private — members only"


class JoinPolicy(models.TextChoices):
    OPEN = "open", "Anyone can join"
    APPROVAL = "approval", "Organizer approval required"
    INVITE = "invite", "Invitation only"


class MemberRole(models.TextChoices):
    MEMBER = "member", "Member"
    ORGANIZER = "organizer", "Organizer"


class MemberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PENDING = "pending", "Awaiting approval"


class Group(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_groups")
    visibility = models.CharField(max_length=12, choices=GroupVisibility.choices, default=GroupVisibility.PUBLIC)
    join_policy = models.CharField(max_length=12, choices=JoinPolicy.choices, default=JoinPolicy.APPROVAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(visibility__in=GroupVisibility.values), name="group_valid_visibility"),
            models.CheckConstraint(condition=models.Q(join_policy__in=JoinPolicy.values), name="group_valid_join_policy"),
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
        return self.visibility != GroupVisibility.PRIVATE or self.owner_id == user.pk or self.memberships.filter(user=user, status=MemberStatus.ACTIVE).exists()

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
