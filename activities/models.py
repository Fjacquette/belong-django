from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, URLValidator
from django.db import models
from django.utils import timezone

from media_assets.models import ImageAssetPurpose


class DemoSeedRecord(models.Model):
    """Explicit ownership of records created by the local demo seeder."""

    key = models.CharField(max_length=160, unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey("content_type", "object_id")


class ActivityCategory(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=160, blank=True)
    hero_image = models.CharField(max_length=255, blank=True)
    color_primary = models.CharField(max_length=7, default="#5b1fa6")
    color_secondary = models.CharField(max_length=7, default="#311b92")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class ActivityVisibility(models.TextChoices):
    EVERYONE = "everyone", "Everyone"
    FRIENDS = "friends", "Friends"
    EXTENDED_FRIENDS = "extended_friends", "Friends of friends"
    GROUP = "group", "Group members"
    CUSTOM = "custom", "Selected friends"


class ActivityLocationType(models.TextChoices):
    IN_PERSON = "in_person", "In person"
    ONLINE = "online", "Online"
    HYBRID = "hybrid", "Hybrid"
    TBD = "tbd", "TBD"


PILOT_AUDIENCE_CHOICES = [
    choice for choice in ActivityVisibility.choices
    if choice[0] in {
        ActivityVisibility.EVERYONE, ActivityVisibility.FRIENDS, ActivityVisibility.EXTENDED_FRIENDS,
    }
]


class ActivityCostType(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    FREE = "free", "Free"
    PAID = "paid", "Paid"


class ActivityResponseStatus(models.TextChoices):
    INTERESTED = "interested", "Interested"
    COMMITTED = "committed", "Count me in"
    QUESTION = "question", "I have a question"
    DECLINED = "declined", "Cannot make it"
    MORE = "more", "Tell me more"
    VOTE = "vote", "Vote on details"


DEFAULT_RESPONSE_CHOICES = [
    ActivityResponseStatus.INTERESTED,
    ActivityResponseStatus.COMMITTED,
    ActivityResponseStatus.QUESTION,
]


class Activity(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hosted_activities",
    )
    title = models.CharField(max_length=160)
    headline = models.CharField(max_length=160, blank=True)
    description = models.TextField()
    summary = models.TextField(blank=True)
    category = models.ForeignKey(
        ActivityCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    multiple_events = models.BooleanField(default=False)
    freetext_when = models.CharField(max_length=160, blank=True)
    post_until = models.DateTimeField(null=True, blank=True)
    location_type = models.CharField(
        max_length=20,
        choices=ActivityLocationType.choices,
        default=ActivityLocationType.TBD,
    )
    location_url = models.URLField(blank=True)
    location_name = models.CharField(max_length=200, blank=True)
    location_address1 = models.CharField(max_length=200, blank=True)
    location_address2 = models.CharField(max_length=200, blank=True)
    location_city = models.CharField(max_length=120, blank=True)
    location_state = models.CharField(max_length=120, blank=True)
    location_zip = models.CharField(max_length=20, blank=True)
    location_phone = models.CharField(max_length=40, blank=True)
    location_gps = models.CharField(max_length=120, blank=True)
    location_instructions = models.TextField(blank=True)
    organizer_image = models.ForeignKey(
        "media_assets.ImageAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizer_activities",
        limit_choices_to={"purpose": ImageAssetPurpose.ORGANIZER},
    )
    organizer_name = models.CharField(max_length=160, blank=True)
    audience = models.CharField(
        max_length=40,
        choices=ActivityVisibility.choices,
        default=ActivityVisibility.EVERYONE,
    )
    allow_friend_invites = models.BooleanField(default=True)
    allow_friend_of_friend_invites = models.BooleanField(default=False)
    is_personal_invitation = models.BooleanField(default=False)
    cost_type = models.CharField(max_length=12, choices=ActivityCostType.choices, default=ActivityCostType.UNKNOWN)
    cost_display = models.CharField(max_length=120, blank=True)
    cost_has_details = models.BooleanField(default=False)
    accommodations = models.TextField(blank=True)
    restrictions = models.TextField(blank=True)
    header_image = models.ForeignKey(
        "media_assets.ImageAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="header_activities",
        limit_choices_to={"purpose": ImageAssetPurpose.ACTIVITY_HEADER},
    )
    color_primary = models.CharField(max_length=7, blank=True)
    color_secondary = models.CharField(max_length=7, blank=True)
    action1_label = models.CharField(max_length=80, blank=True)
    action1_url = models.CharField(max_length=255, blank=True, validators=[URLValidator(schemes=["http", "https"])])
    action2_label = models.CharField(max_length=80, blank=True)
    action2_url = models.CharField(max_length=255, blank=True, validators=[URLValidator(schemes=["http", "https"])])
    action3_label = models.CharField(max_length=80, blank=True)
    action3_url = models.CharField(max_length=255, blank=True, validators=[URLValidator(schemes=["http", "https"])])
    available_responses = models.JSONField(default=list, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at", "-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return self.title

    def active_responses(self):  # pragma: no cover - helper for templates later
        if not self.available_responses:
            return [status.value for status in DEFAULT_RESPONSE_CHOICES]
        if not isinstance(self.available_responses, list):
            return []
        return [status for status in self.available_responses if status in ActivityResponseStatus.values]

    def _action_href(self, value):
        try:
            URLValidator(schemes=["http", "https"])(value)
        except ValidationError:
            return "#"
        return value

    def action1_href(self):
        return self._action_href(self.action1_url)

    def action2_href(self):
        return self._action_href(self.action2_url)

    def action3_href(self):
        return self._action_href(self.action3_url)

    def visible_until(self):  # pragma: no cover
        if self.post_until:
            return self.post_until
        if self.starts_at:
            return self.starts_at
        return timezone.now() + timezone.timedelta(hours=24)

    def organizer_image_url(self) -> str | None:
        if self.organizer_image:
            return self.organizer_image.get_absolute_url()
        return None

    def header_image_url(self) -> str | None:
        if self.header_image:
            return self.header_image.get_absolute_url()
        return None


class ActivityResponse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    status = models.CharField(
        max_length=20,
        choices=ActivityResponseStatus.choices,
        default=ActivityResponseStatus.INTERESTED,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "activity")
        ordering = ["-updated_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user} -> {self.activity} ({self.status})"


class HiddenActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hidden_activities")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="hidden_preferences")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "activity"), name="unique_hidden_activity")]
