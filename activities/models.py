from decimal import Decimal
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
    INTERESTED = "interested", "Interested (historical)"
    COMMITTED = "committed", "Count me in"
    QUESTION = "question", "I have a question"
    DECLINED = "declined", "Cannot make it"
    MORE = "more", "Tell me more"
    VOTE = "vote", "Vote on details"


DEFAULT_RESPONSE_CHOICES = [
    ActivityResponseStatus.MORE,
]

CURRENT_RESPONSE_CHOICES = [choice for choice in ActivityResponseStatus.choices if choice[0] != ActivityResponseStatus.INTERESTED]


def current_response_values(values):
    if not isinstance(values, list):
        return []
    allowed = {value for value, label in CURRENT_RESPONSE_CHOICES}
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value in allowed))


class ActivityStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CANCELLED = 'cancelled', 'Cancelled'


class Activity(models.Model):
    status = models.CharField(max_length=12, choices=ActivityStatus.choices, default=ActivityStatus.ACTIVE, db_default=ActivityStatus.ACTIVE)
    cancellation_reason = models.TextField(max_length=500, blank=True, default='', db_default='')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_activities')
    interests = models.ManyToManyField("social.Interest", blank=True, related_name="activities")
    series = models.ForeignKey('ActivitySeries', on_delete=models.SET_NULL, null=True, blank=True, related_name='occurrences')
    group = models.ForeignKey(
        "groups.Group", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="activities",
    )
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
        choices=PILOT_AUDIENCE_CHOICES,
        default=ActivityVisibility.EVERYONE,
    )
    allow_friend_invites = models.BooleanField(default=True)
    allow_friend_of_friend_invites = models.BooleanField(default=False)
    is_personal_invitation = models.BooleanField(default=False)
    cost_type = models.CharField(max_length=12, choices=ActivityCostType.choices, default=ActivityCostType.UNKNOWN)
    cost_amount = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))], help_text="Amount per person in USD. Leave blank if not yet known.")
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
    invite_group_members = models.BooleanField(default=False, verbose_name='Invite active group members')
    available_responses = models.JSONField(default=list, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at", "-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=ActivityStatus.values), name='activity_valid_status')]

    def __str__(self) -> str:  # pragma: no cover
        return self.title

    def clean(self):
        super().clean()
        if self.cost_type == ActivityCostType.PAID and self.cost_amount == 0:
            raise ValidationError({'cost_type': 'Choose Free for a zero cost.'})

    @property
    def is_cancelled(self):
        return self.status == ActivityStatus.CANCELLED

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('activities:detail', args=[self.pk])

    def can_organize(self, user):
        return user.is_authenticated and (self.host_id == user.pk or bool(self.group_id and self.group.can_organize(user)))

    def active_responses(self):  # pragma: no cover - helper for templates later
        if not self.available_responses:
            return [status.value for status in DEFAULT_RESPONSE_CHOICES]
        return current_response_values(self.available_responses)

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

    @property
    def organizer_display_name(self):
        if self.organizer_name:
            suffix = ' (Organization)' if self.host.profile.account_type == 'organization' else ''
            return self.organizer_name + suffix
        return self.host.profile.identity_label

    def organizer_image_url(self) -> str | None:
        if self.organizer_image:
            return self.organizer_image.get_absolute_url()
        return self.host.profile.avatar_url()

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
        default=ActivityResponseStatus.MORE,
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


class HiddenOrganizer(models.Model):
    """Private Discover suppression; does not affect friendship or participation."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hidden_organizers")
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discovery_suppressions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "organizer"), name="unique_hidden_organizer")]


class ActivitySeries(models.Model):
    """Reusable activity defaults and cadence; occurrences retain independent values."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_series')
    group = models.ForeignKey('groups.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='series')
    title = models.CharField(max_length=160)
    description = models.TextField()
    category = models.ForeignKey(ActivityCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='series')
    audience = models.CharField(max_length=40, choices=PILOT_AUDIENCE_CHOICES, default=ActivityVisibility.EVERYONE)
    invite_group_members = models.BooleanField(default=False, verbose_name='Invite active group members')
    available_responses = models.JSONField(default=list, blank=True)
    location_type = models.CharField(max_length=20, choices=ActivityLocationType.choices, default=ActivityLocationType.TBD)
    location_name = models.CharField(max_length=200, blank=True)
    location_address1 = models.CharField(max_length=200, blank=True)
    location_address2 = models.CharField(max_length=200, blank=True)
    location_city = models.CharField(max_length=120, blank=True)
    location_state = models.CharField(max_length=120, blank=True)
    location_zip = models.CharField(max_length=20, blank=True)
    location_url = models.URLField(blank=True)
    location_gps = models.CharField(max_length=120, blank=True)
    location_instructions = models.TextField(blank=True)
    cost_type = models.CharField(max_length=12, choices=ActivityCostType.choices, default=ActivityCostType.UNKNOWN)
    cost_amount = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))])
    cost_display = models.CharField(max_length=120, blank=True)
    header_image = models.ForeignKey('media_assets.ImageAsset', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='header_series', limit_choices_to={'purpose': ImageAssetPurpose.ACTIVITY_HEADER})
    color_primary = models.CharField(max_length=7, blank=True)
    color_secondary = models.CharField(max_length=7, blank=True)
    cadence = models.CharField(max_length=12, choices=[('flexible', 'As arranged'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='flexible')
    weekday = models.PositiveSmallIntegerField(null=True, blank=True, choices=list(enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])))
    usual_start_time = models.TimeField(null=True, blank=True)
    cadence_description = models.CharField(max_length=160, blank=True, help_text='Optional schedule details, such as the first Saturday of each month.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(cadence__in=['flexible', 'daily', 'weekly', 'monthly']), name='series_valid_cadence'),
            models.CheckConstraint(condition=models.Q(weekday__isnull=True) | models.Q(weekday__lte=6), name='series_valid_weekday'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('activities:series_detail', args=[self.pk])

    def can_organize(self, user):
        if not user.is_authenticated:
            return False
        return self.group.can_organize(user) if self.group_id else self.owner_id == user.pk


class Announcement(models.Model):
    activity = models.ForeignKey(Activity, null=True, blank=True, on_delete=models.CASCADE, related_name='announcements')
    group = models.ForeignKey('groups.Group', null=True, blank=True, on_delete=models.CASCADE, related_name='announcements')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='authored_announcements')
    body = models.TextField(max_length=2000)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='received_announcements', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(
            condition=(models.Q(activity__isnull=False, group__isnull=True)
                       | models.Q(activity__isnull=True, group__isnull=False)),
            name='announcement_exactly_one_context')]

    def clean(self):
        super().clean()
        if bool(self.activity_id) == bool(self.group_id):
            raise ValidationError('Choose exactly one Activity or Group.')


class ActivityInvitation(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='direct_invitations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_invitations')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_activity_invitations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['activity', 'user'], name='unique_activity_invitee')]


class ActivityEmailInvitation(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='email_invitations')
    email = models.EmailField()
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_activity_email_invitations')
    token_digest = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=12, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('revoked', 'Revoked')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_activity_email_invitations')

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['activity', 'email'], name='unique_activity_invitation_email'),
            models.CheckConstraint(condition=models.Q(status__in=['pending', 'accepted', 'revoked']), name='activity_email_invitation_valid_status'),
        ]

    @property
    def display_status(self):
        from django.utils import timezone
        if self.status == 'pending' and self.expires_at <= timezone.now():
            return 'Expired'
        return self.get_status_display()


class GroupJoinOffer(models.Model):
    """One optional post-response offer per person/Group, including durable dismissal."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_group_offers')
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='activity_join_offers')
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, related_name='group_join_offers')
    status = models.CharField(max_length=12, choices=[('pending', 'Pending'), ('dismissed', 'Dismissed'), ('accepted', 'Accepted')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'group'], name='unique_activity_group_join_offer'),
            models.CheckConstraint(condition=models.Q(status__in=['pending', 'dismissed', 'accepted']), name='activity_group_offer_valid_status'),
        ]
