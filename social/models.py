from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from media_assets.models import ImageAssetPurpose

User = settings.AUTH_USER_MODEL


class Interest(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ('section', 'name')

    def __str__(self):
        return self.name


class InterestSuggestion(models.Model):
    profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='interest_suggestions')
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class UserProfile(models.Model):
    interests = models.ManyToManyField(Interest, blank=True, related_name='profiles')
    interests_prompt_pending = models.BooleanField(default=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    account_type = models.CharField(max_length=16, choices=[('individual', 'Individual'), ('organization', 'Organization')], default='individual')
    display_name = models.CharField(max_length=120, default='')
    location = models.CharField(max_length=120, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Only locally provisioned/legacy users; public signup explicitly disables this.
    legacy_access = models.BooleanField(default=False)
    pending_email = models.EmailField(blank=True)
    outbound_mail_suspended = models.BooleanField(default=False, db_default=False)

    @property
    def can_use_belong(self):
        return bool(self.email_verified_at or (settings.ALLOW_LEGACY_ACCOUNTS and self.legacy_access))

    @property
    def identity_label(self):
        name = self.display_name or self.user.get_full_name() or self.user.username
        return f'{name} (Organization)' if self.account_type == 'organization' else name

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


class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verifications')
    email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class EmailControlLock(models.Model):
    """A single durable serialization point for quota reservations."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    touched_at = models.DateTimeField(default=timezone.now)


class OutboundEmailAttempt(models.Model):
    kind = models.CharField(max_length=24, db_index=True)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    recipient_hash = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    group_reference = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    outcome = models.CharField(max_length=24, default='reserved')
    reason = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ('-created_at',)


class AccountEmailProof(models.Model):
    """Public signup/recovery proofs do not reserve an auth.User or store credentials."""
    email = models.EmailField()
    purpose = models.CharField(max_length=16)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
