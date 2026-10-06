from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.template.defaultfilters import slugify
from django.utils import timezone

from activities.models import (
    Activity,
    ActivityCategory,
    ActivityLocationType,
    ActivityResponse,
    ActivityResponseStatus,
    ActivityVisibility,
    DemoSeedRecord,
    DEFAULT_RESPONSE_CHOICES,
)
from media_assets.models import ImageAsset, ImageAssetPurpose
from social.models import FriendGroup, FriendGroupMembership, Friendship, UserProfile

User = get_user_model()


def seed_record(key, model, defaults, *, identity=(), update=True):
    """Never adopt an existing object by username, title, slug, or filename."""
    content_type = ContentType.objects.get_for_model(model)
    record = DemoSeedRecord.objects.select_for_update().filter(key=key).first()
    if record and record.content_type_id != content_type.pk:
        raise CommandError(f"Demo ownership mismatch for {key}; no changes made.")
    obj = record.content_object if record else None
    if obj is not None:
        if any(getattr(obj, field) != defaults[field] for field in identity):
            raise CommandError(f"Demo identity or owner changed for {key}; no changes made.")
        if update:
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save()
        return obj, False
    try:
        obj = model.objects.create(**defaults)
    except IntegrityError as error:
        raise CommandError(f"Existing data conflicts with {key}; no changes made.") from error
    if record:
        record.object_id = str(obj.pk)
        record.save(update_fields=["object_id"])
    else:
        DemoSeedRecord.objects.create(key=key, content_type=content_type, object_id=str(obj.pk))
    return obj, True


@dataclass
class CategorySeed:
    name: str
    slug: str
    tagline: str
    color_primary: str
    color_secondary: str
    hero: str


CATEGORIES: list[CategorySeed] = [
    CategorySeed("Play", "play", "Online and in-person games", "#1565C0", "#42A5F5", "img/categories/play.jpg"),
    CategorySeed("Compete", "compete", "Sports and friendly competition", "#00695C", "#26A69A", "img/categories/compete.jpg"),
    CategorySeed("Go outside", "go-outside", "From leisurely to athletic", "#2E7D32", "#66BB6A", "img/categories/go-outside.jpg"),
    CategorySeed("Move", "move", "Exercise and fitness", "#512DA8", "#9575CD", "img/categories/move.jpg"),
    CategorySeed("Believe", "believe", "Spirituality and reflection", "#4A148C", "#7E57C2", "img/categories/believe.jpg"),
    CategorySeed("Help", "help", "Mutual aid", "#283593", "#5C6BC0", "img/categories/help.jpg"),
    CategorySeed("Be kind", "be-kind", "Volunteering & charity", "#1565C0", "#29B6F6", "img/categories/be-kind.jpg"),
    CategorySeed("Chill", "chill", "Just hang out", "#00695C", "#26A69A", "img/categories/chill.jpg"),
    CategorySeed("Succeed", "succeed", "Career & growth", "#4527A0", "#7E57C2", "img/categories/succeed.jpg"),
    CategorySeed("Create", "create", "Create art online or in-person", "#8E24AA", "#CE93D8", "img/categories/create.jpg"),
    CategorySeed("Explore", "explore", "Experience something new", "#0277BD", "#26C6DA", "img/categories/explore.jpg"),
    CategorySeed("Adventure", "adventure", "Be bold and go somewhere", "#006064", "#00838F", "img/categories/adventure.jpg"),
    CategorySeed("Grow", "grow", "Learning & improvement", "#2E7D32", "#66BB6A", "img/categories/grow.jpg"),
    CategorySeed("Entertain", "entertain", "Performance & comedy", "#AD1457", "#F06292", "img/categories/entertain.jpg"),
    CategorySeed("Dream", "dream", "Be amazing", "#4A148C", "#7B1FA2", "img/categories/dream.jpg"),
    CategorySeed("Invent", "invent", "Build something awesome", "#BF360C", "#FF7043", "img/categories/invent.jpg"),
    CategorySeed("Change", "change", "Activism & politics", "#880E4F", "#C2185B", "img/categories/change.jpg"),
    CategorySeed("Find", "find", "Folks with common interests", "#6A1B9A", "#AB47BC", "img/categories/find.jpg"),
    CategorySeed("Improvise", "improvise", "Do something right now", "#4527A0", "#7B1FA2", "img/categories/improvise.jpg"),
    CategorySeed("Surprise me", "surprise", "Take a chance", "#512DA8", "#9575CD", "img/categories/surprise.jpg"),
]


def load_image_asset(relative_path: str | None, *, purpose: str, name: str) -> ImageAsset | None:
    if not relative_path:
        return None

    stem = Path(relative_path).stem.replace("-", "_")
    stem = {"go_outside": "get_outside", "find": "find_your_tribe"}.get(stem, stem)
    candidates = [Path(settings.BASE_DIR, "static", relative_path)]
    candidates.extend(
        Path(settings.BASE_DIR, "mock_images", name)
        for name in (f"{stem}_image.jpg", f"{stem}.jpg", f"{stem}.png")
    )
    asset_path = next((path for path in candidates if path.is_file()), None)
    if asset_path is None:
        return None

    payload = asset_path.read_bytes()
    content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"

    asset, _ = seed_record(
        f"image:{purpose}:{relative_path}",
        ImageAsset,
        {
            "name": name,
            "purpose": purpose,
            "filename": relative_path,
            "data": payload,
            "content_type": content_type,
            "size": len(payload),
        },
    )

    return asset


def ensure_users(users: Iterable[dict]):
    created_users = {}
    for data in users:
        seed_name = data["username"]
        username = "belong_demo" if seed_name == "demo" else f"belong_demo_{seed_name}"
        user, created = seed_record(
            f"user:{seed_name}", User,
            {
                "username": username,
                "email": f"{username}@example.invalid",
                "is_staff": data.get("is_staff", False),
                "is_superuser": data.get("is_superuser", False),
            },
            identity=("username",), update=False,
        )
        if created:
            if data.get("password"):
                user.set_password(data["password"])
            else:
                user.set_unusable_password()
            user.save(update_fields=["password"])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.status_text = data.get("status_text", profile.status_text)
        profile.is_visible = data.get("is_visible", True)
        if data.get("last_active_delta"):
            profile.last_active_at = timezone.now() - data["last_active_delta"]
        else:
            profile.last_active_at = timezone.now()
        profile.status_updated_at = timezone.now()

        avatar_asset = load_image_asset(
            data.get("avatar"),
            purpose=ImageAssetPurpose.PROFILE_AVATAR,
            name=f"{username} avatar",
        )
        if avatar_asset:
            profile.avatar_image = avatar_asset

        profile.save()
        created_users[seed_name] = user
    return created_users



def ensure_friendships(user_map: dict[str, User], pairs: Iterable[tuple[str, str]]):
    for a, b in pairs:
        user_a, user_b = sorted((user_map[a], user_map[b]), key=lambda user: user.pk)
        seed_record(
            f"friendship:{a}:{b}", Friendship, {"user_a": user_a, "user_b": user_b},
            identity=("user_a", "user_b"), update=False,
        )


def aware(dt: datetime | None):
    if not dt:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

ACTIVITY_DATA = [
    {
        "title": "Sailing on weekends!",
        "headline": "Find a first mate",
        "category": "go-outside",
        "multiple_events": True,
        "freetext_when": "Summer weekends",
        "location_type": ActivityLocationType.IN_PERSON,
        "location_city": "Ellicott City",
        "location_state": "MD",
        "organizer": "Jonas Grumby",
        "organizer_image": "img/organizers/jonas.png",
        "audience": ActivityVisibility.FRIENDS,
        "cost_display": "Free (see details)",
        "cost_has_details": True,
        "summary": "Looking for friends to hang out with me on my boat most weekends during the season.",
        "description": "Looking for friends to hang out with me on my boat most weekends during the season. Generally sail for three hour tours, weather permitting. No skills necessary, bring your own snacks and beverages.",
        "color_primary": "#7034A2",
        "color_secondary": "#0570C0",
        "action1_label": "I'm interested",
    },
    {
        "title": "Chill Overwatch 2",
        "headline": "Casual game night",
        "category": "play",
        "freetext_when": "Now",
        "location_type": ActivityLocationType.ONLINE,
        "location_url": "https://discord.gg/cjeGwmT8",
        "organizer": "Frank Jacquette",
        "organizer_image": "img/organizers/frank.png",
        "audience": ActivityVisibility.EVERYONE,
        "summary": "Come join us for some chill Overwatch 2 games.",
        "description": "Come join us for some chill Overwatch 2 games. All skills welcome, we'll play until about 10 PM ET.",
        "action1_label": "Join on Discord",
        "action1_url": "https://discord.gg/cjeGwmT8",
    },
    {
        "title": "Hersheypark trip",
        "headline": "Plan a summer getaway",
        "category": "adventure",
        "freetext_when": "TBD",
        "organizer": "Carol Brady",
        "organizer_image": "img/organizers/carol.png",
        "audience": ActivityVisibility.EXTENDED_FRIENDS,
        "summary": "We want to get a group together to go to Hersheypark one day in July.",
        "description": "No dates yet—drop your interest level and we'll coordinate the best weekend.",
        "color_primary": "#0C6A8F",
        "color_secondary": "#18A3B9",
        "action1_label": "Tell me more",
    },
    {
        "title": "Need help moving",
        "headline": "Boxes, pizza, friends",
        "category": "help",
        "freetext_when": "Next Saturday",
        "location_type": ActivityLocationType.IN_PERSON,
        "location_city": "King of Prussia",
        "location_state": "PA",
        "organizer": "Greg Brady",
        "organizer_image": "img/organizers/greg.png",
        "audience": ActivityVisibility.FRIENDS,
        "summary": "Need some extra hands to move apartments. Pizza and thank-yous provided!",
        "description": "We'll have a truck, just need muscles. Bring gloves if you have them.",
        "action1_label": "Help Greg",
    },
    {
        "title": "Co-ed softball league",
        "headline": "Forming now",
        "category": "compete",
        "multiple_events": True,
        "freetext_when": "April through September",
        "location_type": ActivityLocationType.IN_PERSON,
        "location_name": "Phoenixville YMCA",
        "location_city": "Phoenixville",
        "location_state": "PA",
        "organizer": "Phoenixville Y",
        "audience": ActivityVisibility.EVERYONE,
        "cost_display": "$60",
        "summary": "All skill levels welcome, games weekly Monday–Thursday evenings.",
        "description": "Co-ed softball league forming, all ages 18+. $60 league fee per person, we provide balls and umpires. Bring a team or sign up as an individual.",
        "action1_label": "Join league",
        "action2_label": "Contact coordinator",
    },
    {
        "title": "Greg is bored",
        "headline": "Find something fun",
        "category": "chill",
        "freetext_when": "Now",
        "location_type": ActivityLocationType.IN_PERSON,
        "location_city": "Newark",
        "location_state": "DE",
        "organizer": "Greg Brady",
        "organizer_image": "img/organizers/greg.png",
        "audience": ActivityVisibility.EXTENDED_FRIENDS,
        "summary": "It's Friday night and I'm bored. Who's up for something?",
        "description": "Ping me if you have ideas — I'm game for anything low-key tonight.",
        "action1_label": "Message Greg",
    },
    {
        "title": "Firefighter flashover training",
        "headline": "Stay sharp",
        "category": "succeed",
        "starts_at": datetime(2025, 6, 4, 8, 0),
        "location_type": ActivityLocationType.IN_PERSON,
        "location_name": "Tactical Village - Flashover Simulator",
        "location_address1": "137 Modena Road",
        "location_city": "Coatesville",
        "location_state": "PA",
        "location_phone": "610-344-4100",
        "organizer": "Chester County EMS",
        "audience": ActivityVisibility.EVERYONE,
        "cost_display": "$100",
        "summary": "8-hour course covering flashover recognition and response.",
        "description": "This course gives firefighters the skills to recognize, understand, and react appropriately to flashover conditions. Live fire evolutions conclude the course. Prerequisite: Live fire training certificate.",
        "restrictions": "Must have firefighter training; full turnout gear and SCBA required.",
        "action1_label": "Register for class",
    },
    {
        "title": "Wednesday night paddle",
        "headline": "Schuylkill River social paddle",
        "category": "go-outside",
        "starts_at": datetime(2025, 5, 4, 18, 0),
        "location_type": ActivityLocationType.IN_PERSON,
        "location_city": "Douglassville",
        "location_state": "PA",
        "organizer": "Take It Outdoors Adventures",
        "audience": ActivityVisibility.EVERYONE,
        "cost_display": "$10 (see details)",
        "cost_has_details": True,
        "summary": "Each Wednesday we gather for a social paddle on the Schuylkill River.",
        "description": "Meet at Union Meadows East in Douglassville. Shuttle upriver then paddle 4.5 miles back through the 'Tunnel of Love'. $10 to participate; kayak rentals +$30.",
        "restrictions": "Must register at https://takeitoutdoorsadventures.com/wednesday/",
        "action1_label": "Hold my spot",
        "action1_url": "https://takeitoutdoorsadventures.com/wednesday/",
    },
    {
        "title": "Stroll the Street - Manayunk",
        "headline": "Thursday night vibes",
        "category": "entertain",
        "starts_at": datetime(2025, 6, 1, 17, 0),
        "location_type": ActivityLocationType.IN_PERSON,
        "location_city": "Manayunk",
        "location_state": "PA",
        "organizer": "Neighborhood Collective",
        "audience": ActivityVisibility.EVERYONE,
        "summary": "Join us for food trucks, art vendors, and live music along Main Street.",
        "description": "Family-friendly evening with rotating vendors every week. Meet at the canal steps and we'll wander together.",
        "action1_label": "RSVP",
    },
]


# Explicit pilot demo semantics, not inference from arbitrary user cost prose.
DEMO_DISCOVERY = {'Sailing on weekends!': ('free', '39.267,-76.798', ['interested', 'more']),
 'Chill Overwatch 2': ('free', '', ['committed', 'question']),
 'Hersheypark trip': ('paid', '40.288,-76.656', ['interested', 'vote', 'question']),
 'Need help moving': ('free', '40.121,-75.339', ['committed', 'more']),
 'Co-ed softball league': ('paid', '40.130,-75.514', ['committed', 'declined']),
 'Greg is bored': ('unknown', '40.028,-75.174', ['interested', 'vote']),
 'Firefighter flashover training': ('paid', '39.962,-75.606', ['committed', 'question']),
 'Wednesday night paddle': ('paid', '40.248,-75.649', ['committed', 'question']),
 'Stroll the Street - Manayunk': ('free', '40.028,-75.225', ['interested', 'more'])}
for example in ACTIVITY_DATA:
    cost, gps, responses = DEMO_DISCOVERY[example["title"]]
    example.update(cost_type=cost, location_gps=gps, available_responses=responses,
                   cost_amount={"Co-ed softball league": 60, "Firefighter flashover training": 100, "Wednesday night paddle": 10}.get(example["title"], 0 if cost == "free" else None))


class Command(BaseCommand):
    help = "Safely create or refresh known demo records in local dev/test only"

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.ENVIRONMENT not in {"dev", "test"}:
            raise CommandError("Demo seeding is allowed only in local dev/test environments.")

        base_users = ensure_users(
            [
                {"username": "admin", "password": "admin123", "is_staff": True, "is_superuser": True},
                {"username": "demo", "password": "demo123"},
                {
                    "username": "stephi",
                    "status_text": "Playing RE4 on Quest.",
                    "avatar": "img/friends/stephi.jpg",
                    "last_active_delta": timedelta(days=90),
                },
                {
                    "username": "rainer",
                    "status_text": "I'm bored. Message me.",
                    "avatar": "img/friends/rainer.jpg",
                    "last_active_delta": timedelta(days=60),
                },
                {
                    "username": "glyn",
                    "status_text": "Posted the next set of night hikes.",
                    "avatar": "img/friends/glyn.jpg",
                    "last_active_delta": timedelta(days=30),
                },
                {
                    "username": "valaree",
                    "status_text": "Traveling for work.",
                    "avatar": "img/friends/valaree.jpg",
                    "last_active_delta": timedelta(days=365),
                },
            ]
        )

        demo = base_users["demo"]

        friend_pairs = [
            ("demo", "stephi"),
            ("demo", "rainer"),
            ("demo", "glyn"),
            ("demo", "valaree"),
            ("stephi", "rainer"),
        ]
        ensure_friendships(base_users, friend_pairs)

        # Default friend groups for demo user
        group_definitions = {
            "Cousins": ["glyn", "valaree"],
            "Gaming crew": ["stephi", "rainer"],
            "Adventurers": ["glyn"],
        }
        for group_name, members in group_definitions.items():
            group, _ = seed_record(
                f"group:{slugify(group_name)}", FriendGroup,
                {"owner": demo, "name": group_name}, identity=("owner",),
            )
            for username in members:
                seed_record(
                    f"membership:{slugify(group_name)}:{username}", FriendGroupMembership,
                    {"group": group, "friend": base_users[username]},
                    identity=("group", "friend"), update=False,
                )

        # Categories
        category_map = {}
        for seed in CATEGORIES:
            category, _ = seed_record(
                f"category:{seed.slug}", ActivityCategory,
                {
                    "slug": f"belong-demo-{seed.slug}",
                    "name": seed.name,
                    "tagline": seed.tagline,
                    "hero_image": (
                        seed.hero if Path(settings.BASE_DIR, "static", seed.hero).is_file() else ""
                    ),
                    "color_primary": seed.color_primary,
                    "color_secondary": seed.color_secondary,
                },
            )
            category_map[seed.slug] = category

        # Activities
        for payload in ACTIVITY_DATA:
            organizer_name = payload.get("organizer") or "Belong Host"
            organizer_username = slugify(organizer_name)
            organizer_user = base_users.get(organizer_username)
            if not organizer_user:
                organizer_user = ensure_users(
                    [{"username": organizer_username, "status_text": ""}]
                )[organizer_username]
                base_users[organizer_username] = organizer_user
            if payload.get("audience") in {
                ActivityVisibility.FRIENDS, ActivityVisibility.EXTENDED_FRIENDS,
            }:
                ensure_friendships(base_users, [("demo", organizer_username)])

            organizer_asset = load_image_asset(
                payload.get("organizer_image"),
                purpose=ImageAssetPurpose.ORGANIZER,
                name=f"{organizer_name} organizer",
            )
            category = category_map.get(payload.get("category"))
            category_seed = next(
                (seed for seed in CATEGORIES if seed.slug == payload.get("category")), None
            )
            header_asset = load_image_asset(
                payload.get("header_image") or (category_seed.hero if category_seed else None),
                purpose=ImageAssetPurpose.ACTIVITY_HEADER,
                name=f"{payload['title']} header",
            )

            activity, _ = seed_record(
                f"activity:{slugify(payload['title'])}", Activity,
                dict(
                    host=organizer_user,
                    title=payload["title"],
                    headline=payload.get("headline", ""),
                    summary=payload.get("summary", ""),
                    description=payload["description"],
                    category=category,
                    starts_at=aware(payload.get("starts_at")),
                    multiple_events=payload.get("multiple_events", False),
                    freetext_when=payload.get("freetext_when", ""),
                    location_type=payload.get("location_type", ActivityLocationType.TBD),
                    location_url=payload.get("location_url", ""),
                    location_name=payload.get("location_name", ""),
                    location_address1=payload.get("location_address1", ""),
                    location_address2=payload.get("location_address2", ""),
                    location_city=payload.get("location_city", ""),
                    location_state=payload.get("location_state", ""),
                    location_zip=payload.get("location_zip", ""),
                    location_phone=payload.get("location_phone", ""),
                    location_gps=payload.get("location_gps", ""),
                    location_instructions=payload.get("location_instructions", ""),
                    organizer_image=organizer_asset,
                    organizer_name=organizer_name,
                    audience=payload.get("audience", ActivityVisibility.EVERYONE),
                    allow_friend_invites=payload.get("allow_friend_invites", True),
                    allow_friend_of_friend_invites=payload.get("allow_friend_of_friend_invites", False),
                    is_personal_invitation=payload.get("is_personal_invitation", False),
                    cost_type=payload["cost_type"],
                    cost_amount=payload.get("cost_amount"),
                    cost_display=payload.get("cost_display", ""),
                    cost_has_details=payload.get("cost_has_details", False),
                    accommodations=payload.get("accommodations", ""),
                    restrictions=payload.get("restrictions", ""),
                    header_image=header_asset,
                    color_primary=payload.get("color_primary", ""),
                    color_secondary=payload.get("color_secondary", ""),
                    action1_label=payload.get("action1_label", ""),
                    action1_url=payload.get("action1_url", ""),
                    action2_label=payload.get("action2_label", ""),
                    action2_url=payload.get("action2_url", ""),
                    action3_label=payload.get("action3_label", ""),
                    action3_url=payload.get("action3_url", ""),
                    available_responses=payload.get(
                        "available_responses",
                        list(DEFAULT_RESPONSE_CHOICES),
                    ),
                    post_until=(
                        aware(payload.get("post_until")) or aware(payload.get("starts_at"))
                        or timezone.now() + timedelta(days=30)
                    ),
                ),
                identity=("host",),
            )

            # New sample responses use the activity's first meaningful choice.
            # Existing responses remain private user state and are never reset.
            seed_record(
                f"response:{slugify(payload['title'])}:demo", ActivityResponse,
                {"user": demo, "activity": activity, "status": activity.active_responses()[0]},
                identity=("user", "activity"), update=False,
            )

        self.stdout.write(self.style.SUCCESS("Known demo data refreshed; other records preserved."))
        self.stdout.write(self.style.SUCCESS(
            "Local-only initial credentials: belong_demo_admin/admin123, belong_demo/demo123"
        ))
