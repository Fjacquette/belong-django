from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from media_assets.models import ImageAssetPurpose

User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    status_text = models.CharField(max_length=160, blank=True)
    is_visible = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    status_updated_at = models.DateTimeField(default=timezone.now)
    avatar_image = models.ForeignKey(
        "media_assets.ImageAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
        limit_choices_to={"purpose": ImageAssetPurpose.PROFILE_AVATAR},
    )

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self) -> str:  # pragma: no cover
        return f"Profile for {self.user}"

    def mark_active(self):  # pragma: no cover helper
        self.last_active_at = timezone.now()
        self.save(update_fields=["last_active_at"])

    def avatar_url(self) -> str | None:
        if self.avatar_image:
            return self.avatar_image.get_absolute_url()
        return None


class FriendRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    CANCELED = "canceled", "Canceled"


class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_friend_requests")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=20, choices=FriendRequestStatus.choices, default=FriendRequestStatus.PENDING)
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("sender", "recipient")
        ordering = ("-created_at",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.sender} ➜ {self.recipient} ({self.status})"


class Friendship(models.Model):
    user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships_a")
    user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships_b")
    created_at = models.DateTimeField(auto_now_add=True)
    created_via_request = models.ForeignKey(
        FriendRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="friendships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user_a", "user_b"), name="unique_friendship_pair"),
            models.CheckConstraint(check=~models.Q(user_a=models.F("user_b")), name="no_self_friendships"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Friendship({self.user_a_id}, {self.user_b_id})"

    @staticmethod
    def make_pair(user1, user2, **kwargs):  # pragma: no cover helper
        if user1.id <= user2.id:
            return Friendship.objects.get_or_create(user_a=user1, user_b=user2, defaults=kwargs)
        return Friendship.objects.get_or_create(user_a=user2, user_b=user1, defaults=kwargs)


class FriendGroup(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_groups")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    cloned_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clones",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "name")
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.owner})"

    def clone(self, new_name: str) -> "FriendGroup":  # pragma: no cover helper
        clone = FriendGroup.objects.create(owner=self.owner, name=new_name, cloned_from=self)
        memberships = [
            FriendGroupMembership(group=clone, friend=m.friend, notes=m.notes)
            for m in self.memberships.all()
        ]
        FriendGroupMembership.objects.bulk_create(memberships)
        return clone


class FriendGroupMembership(models.Model):
    group = models.ForeignKey(FriendGroup, on_delete=models.CASCADE, related_name="memberships")
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_group_memberships")
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "friend")
        ordering = ["friend__username"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.friend} in {self.group}"
