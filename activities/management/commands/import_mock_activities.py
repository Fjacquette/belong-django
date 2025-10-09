from __future__ import annotations

import json
import mimetypes
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from activities.models import Activity, ActivityCategory, ActivityLocationType, ActivityVisibility
from media_assets.models import ImageAsset, ImageAssetPurpose
from social.models import UserProfile

User = get_user_model()


@dataclass(slots=True)
class MockRecord:
    raw: dict

    @property
    def title(self) -> str:
        return self.raw.get("headline") or "Untitled activity"

    @property
    def category_names(self) -> Iterable[str]:
        value = self.raw.get("category") or []
        if isinstance(value, str):
            return [value]
        return value

    @property
    def organizer(self) -> str:
        return self.raw.get("organizer") or "Unknown Organizer"


class Command(BaseCommand):
    help = "Import mock React activity data, creating ImageAsset records automatically."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data",
            type=str,
            default=str(Path(settings.BASE_DIR, "scripts", "mock_activities.json")),
            help="Path to JSON payload with mock activity data.",
        )
        parser.add_argument(
            "--images",
            type=str,
            default=str(Path(settings.BASE_DIR, "mock_images")),
            help="Directory containing image files referenced in the JSON.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove previously imported mock activities before loading new ones.",
        )

    def handle(self, *args, **options):
        data_path = Path(options["data"])
        image_root = Path(options["images"])

        if not data_path.exists():
            raise CommandError(f"Data file not found: {data_path}")

        with data_path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)

        if not isinstance(payload, list):
            raise CommandError("JSON payload must be a list of activity definitions.")

        if options["reset"]:
            self._purge_existing(payload)

        categories = self._category_lookup()
        stats = defaultdict(int)

        for entry in payload:
            record = MockRecord(entry)
            activity, created = self._upsert_activity(record, image_root, categories)
            stats["created" if created else "updated"] += 1

        self.stdout.write(self.style.SUCCESS(f"Imported mock activities: {stats['created']} created, {stats['updated']} updated."))

    def _purge_existing(self, payload: list[dict]):
        titles = [MockRecord(entry).title for entry in payload]
        deleted, _ = Activity.objects.filter(title__in=titles).delete()
        self.stdout.write(self.style.WARNING(f"Removed {deleted} existing activity rows."))

    def _category_lookup(self) -> dict[str, ActivityCategory]:
        lookup: dict[str, ActivityCategory] = {}
        for category in ActivityCategory.objects.all():
            key = category.slug.lower()
            lookup[key] = category
        return lookup

    def _upsert_activity(self, record: MockRecord, image_root: Path, categories: dict[str, ActivityCategory]):
        organizer_user = self._ensure_user(record, image_root)
        organizer_asset = self._ensure_image_asset(
            image_root,
            record.raw.get("organizer_image"),
            purpose=ImageAssetPurpose.ORGANIZER,
            default_name=f"{record.organizer} organizer",
        )
        header_asset = self._ensure_image_asset(
            image_root,
            record.raw.get("header_image"),
            purpose=ImageAssetPurpose.ACTIVITY_HEADER,
            default_name=f"{record.title} header",
        )

        category = self._resolve_category(record, categories)
        defaults = self._build_activity_defaults(record, organizer_user, organizer_asset, header_asset, category)

        activity, created = Activity.objects.update_or_create(
            title=record.title,
            defaults=defaults,
        )
        return activity, created

    def _ensure_user(self, record: MockRecord, image_root: Path) -> User:
        organizer_name = record.organizer.strip()
        username = slugify(organizer_name) or "organizer"

        defaults = {}
        if " " in organizer_name:
            parts = organizer_name.split()
            defaults["first_name"] = parts[0]
            defaults["last_name"] = " ".join(parts[1:])
        else:
            defaults["first_name"] = organizer_name

        user, _ = User.objects.get_or_create(username=username, defaults=defaults)
        profile, _ = UserProfile.objects.get_or_create(user=user)

        avatar_asset = self._ensure_image_asset(
            image_root,
            record.raw.get("organizer_image"),
            purpose=ImageAssetPurpose.PROFILE_AVATAR,
            default_name=f"{organizer_name} avatar",
        )
        if avatar_asset and profile.avatar_image_id != avatar_asset.id:
            profile.avatar_image = avatar_asset
            profile.save(update_fields=["avatar_image"])

        return user

    def _ensure_image_asset(self, image_root: Path, filename: str | None, *, purpose: str, default_name: str) -> ImageAsset | None:
        if not filename:
            return None

        path_options = [
            Path(filename),
            image_root / filename,
            Path(settings.BASE_DIR, "static", filename),
        ]

        asset_path = next((path for path in path_options if path.exists()), None)
        if not asset_path:
            self.stderr.write(self.style.WARNING(f"Image file not found for {filename}; using fallback."))
            return None

        payload = asset_path.read_bytes()
        content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"

        asset, created = ImageAsset.objects.get_or_create(
            filename=asset_path.name,
            purpose=purpose,
            defaults={
                "name": default_name,
                "data": payload,
                "content_type": content_type,
                "size": len(payload),
            },
        )

        if not created:
            updates: list[str] = []
            if asset.size != len(payload):
                asset.data = payload
                asset.size = len(payload)
                updates.extend(["data", "size"])
            if asset.content_type != content_type:
                asset.content_type = content_type
                updates.append("content_type")
            if default_name and asset.name != default_name:
                asset.name = default_name
                updates.append("name")
            if updates:
                asset.save(update_fields=list(dict.fromkeys(updates)))

        return asset

    def _resolve_category(self, record: MockRecord, categories: dict[str, ActivityCategory]) -> ActivityCategory | None:
        for raw_name in record.category_names:
            slug = slugify(raw_name)
            category = categories.get(slug)
            if category:
                return category
        return None

    def _build_activity_defaults(
        self,
        record: MockRecord,
        organizer_user: User,
        organizer_asset: ImageAsset | None,
        header_asset: ImageAsset | None,
        category: ActivityCategory | None,
    ) -> dict:
        data = record.raw
        starts_at = parse_datetime(data.get("start") or "") or None
        ends_at = parse_datetime(data.get("end") or "") or None
        post_until = parse_datetime(data.get("post_until") or "") or None

        if post_until and timezone.is_naive(post_until):
            post_until = timezone.make_aware(post_until, timezone.get_current_timezone())
        if starts_at and timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        if ends_at and timezone.is_naive(ends_at):
            ends_at = timezone.make_aware(ends_at, timezone.get_current_timezone())

        cost_value = data.get("cost")
        cost_display = ""
        if isinstance(cost_value, (int, float)):
            if cost_value > 0:
                cost_display = f"${cost_value:,.0f}"
            elif cost_value == 0:
                cost_display = "Free"

        description = data.get("description") or data.get("summary") or ""
        summary = data.get("summary") or description[:160]

        return {
            "host": organizer_user,
            "headline": data.get("headline") or "",
            "summary": summary,
            "description": description,
            "category": category,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "multiple_events": bool(data.get("multiple_events")),
            "freetext_when": data.get("freetext_when") or "",
            "post_until": post_until,
            "location_type": self._map_location_type(data.get("location_type")),
            "location_url": data.get("location_url") or "",
            "location_name": data.get("location_name") or "",
            "location_address1": data.get("location_address1") or "",
            "location_address2": data.get("location_address2") or "",
            "location_city": data.get("location_city") or "",
            "location_state": data.get("location_state") or "",
            "location_zip": data.get("location_zip") or "",
            "location_phone": data.get("activity_phone") or "",
            "location_instructions": data.get("location_instructions") or "",
            "organizer_image": organizer_asset,
            "organizer_name": record.organizer,
            "audience": self._map_audience(data.get("audience")),
            "cost_display": cost_display,
            "cost_has_details": bool(data.get("cost_see_details")),
            "accommodations": "\n".join(data.get("accommodations") or []),
            "restrictions": "\n".join(data.get("restrictions") or []),
            "header_image": header_asset,
            "color_primary": data.get("color1") or "",
            "color_secondary": data.get("color2") or "",
            "action1_label": data.get("action1_label") or "",
            "action1_url": data.get("action1") or "",
            "action2_label": data.get("action2_label") or "",
            "action2_url": data.get("action2") or "",
            "action3_label": data.get("action3_label") or "",
            "action3_url": data.get("action3") or "",
            "available_responses": [],
        }

    def _map_location_type(self, raw_value: str | None) -> str:
        normalized = (raw_value or "").strip().lower()
        mapping = {
            "in person": ActivityLocationType.IN_PERSON,
            "in-person": ActivityLocationType.IN_PERSON,
            "online": ActivityLocationType.ONLINE,
            "hybrid": ActivityLocationType.HYBRID,
            "tbd": ActivityLocationType.TBD,
        }
        return mapping.get(normalized, ActivityLocationType.TBD)

    def _map_audience(self, raw_value: str | None) -> str:
        normalized = (raw_value or "").strip().lower()
        mapping = {
            "friends": ActivityVisibility.FRIENDS,
            "extended friends": ActivityVisibility.EXTENDED_FRIENDS,
            "extended_friends": ActivityVisibility.EXTENDED_FRIENDS,
            "everyone": ActivityVisibility.EVERYONE,
            "group": ActivityVisibility.GROUP,
        }
        return mapping.get(normalized, ActivityVisibility.EVERYONE)
