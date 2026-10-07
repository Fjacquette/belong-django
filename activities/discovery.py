"""Small, explicit pilot filters; no geospatial service or inferred cost prose."""
from datetime import datetime, time, timedelta
import math
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import ActivityLocationType


def coordinates(value):
    try:
        latitude, longitude = (float(part.strip()) for part in value.split(','))
        if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return latitude, longitude
    except (ValueError, AttributeError):
        pass
    return None


def distance_miles(first, second):
    lat1, lon1, lat2, lon2 = map(math.radians, (*first, *second))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 3958.8 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


FACETS = {
    'when': ('When', [('now', 'Now', ''), ('today', 'Today', ''), ('tomorrow', 'Tomorrow', ''), ('week', 'This week', ''), ('weekend', 'This weekend', ''), ('open', 'Open-ended', '')]),
    'where': ('Where', [('online', 'Online', ''), ('under_1', 'Under 1 mile', ''), ('1_3', '1–3 miles', ''), ('3_5', '3–5 miles', ''), ('5_10', '5–10 miles', ''), ('10_25', '10–25 miles', ''), ('25_plus', '25+ miles', '')]),
    'cost': ('Cost', [('free', 'Free', ''), ('1_10', '$', '$1–10'), ('11_25', '$$', '$11–25'), ('26_50', '$$$', '$26–50'), ('51_100', '$$$$', '$51–100'), ('100_plus', '$$$$$', 'Over $100')]),
    'audience': ('Open to', [('everyone', 'Everyone', ''), ('friends', 'Friends only', ''), ('extended_friends', 'Friends of friends', '')]),
}
DISTANCES = {'under_1': (0, 1), '1_3': (1, 3), '3_5': (3, 5), '5_10': (5, 10), '10_25': (10, 25), '25_plus': (25, math.inf)}


def canonical_filters(params):
    """Normalize repeated facet values; old shortcuts map into the same controls."""
    params = params.copy()
    params.pop("card-view", None)
    if 'when' not in params:
        timing = params.get('timing') if 'timing' in params else 'today' if params.get('today') == '1' else ''
        params.setlist('when', {'today': ['today'], 'dateless': ['open']}.get(timing, []))
    if 'where' not in params:
        where = ['online'] if params.get('location') in ['online', 'online_capable'] or ('location' not in params and params.get('online') == '1') else []
        if params.get('nearby') == '1':
            where.extend(list(DISTANCES)[:5])
        params.setlist('where', where)
    if 'cost' not in params and params.get('free') == '1':
        params.setlist('cost', ['free'])
    elif params.getlist('cost') == ['paid']:
        params.setlist('cost', ['1_10', '11_25', '26_50', '51_100', '100_plus'])
    for key in ['timing', 'location', 'nearby', 'today', 'online', 'free']:
        params.pop(key, None)
    if "hidden" in params:
        params["hidden"] = params.get("hidden") if params.get("hidden") in {"exclude", "include", "only"} else "exclude"
    for name, (_, choices) in FACETS.items():
        allowed = {value for value, _, _ in choices}
        values = list(dict.fromkeys(v for v in params.getlist(name) if v in allowed))
        if values:
            params.setlist(name, values)
        else:
            params.pop(name, None)
    return params


def facet_context(params):
    facets = []
    for name, (label, choices) in FACETS.items():
        selected = params.getlist(name)
        active = [text for value, text, _ in choices if value in selected]
        summary = f"{label} · {active[0]}" if name == "cost" and len(active) == 1 else f"{label} · {len(active)}" if active else label
        facets.append({'name': name, 'label': label, 'summary': summary, 'active': bool(active),
                       'options': [{'value': v, 'label': text, 'help': help_text, 'selected': v in selected,
                                    'distance': v in DISTANCES} for v, text, help_text in choices]})
    return facets


def filter_activities(queryset, params):
    from django.db.models import Q
    nearby, warning = False, ''
    now = timezone.now()
    zone = ZoneInfo(settings.PILOT_TIME_ZONE)
    today = now.astimezone(zone).date()
    midnight = datetime.combine(today, time.min, tzinfo=zone)
    selections = params.getlist('when')
    if selections:
        condition = Q(pk__in=[])
        for value in selections:
            if value == 'now':
                # In-progress events, recent starts with no end, or explicit proto-intent.
                condition |= Q(starts_at__lte=now, ends_at__gt=now) | Q(starts_at__gte=now-timedelta(hours=2), starts_at__lte=now, ends_at__isnull=True) | Q(starts_at__isnull=True, freetext_when__iexact='Now')
            elif value == 'open':
                condition |= Q(starts_at__isnull=True)
            else:
                start, end = midnight, midnight + timedelta(days=1)
                if value == 'tomorrow':
                    start, end = midnight+timedelta(days=1), midnight+timedelta(days=2)
                elif value == 'week':
                    end = midnight+timedelta(days=7-today.weekday())
                elif value == 'weekend':
                    saturday = midnight+timedelta(days=5-today.weekday())
                    start = max(midnight, saturday)
                    end = saturday+timedelta(days=2)
                condition |= Q(starts_at__gte=start, starts_at__lt=end)
        queryset = queryset.filter(condition)
    selections = params.getlist('where')
    buckets = [v for v in selections if v in DISTANCES]
    origin = coordinates(f"{params.get('lat', '')},{params.get('lon', '')}")
    if buckets and origin is None:
        selections = [v for v in selections if v not in DISTANCES]
        if selections:
            params.setlist('where', selections)
        else:
            params.pop('where', None)
        buckets = []
        warning = 'Distance filters are off. Allow location access to use them.'
    if selections:
        condition = Q(pk__in=[])
        if 'online' in selections:
            condition |= Q(location_type__in=[ActivityLocationType.ONLINE, ActivityLocationType.HYBRID])
        if buckets:
            nearby = True
            ids = []
            physical = queryset.filter(location_type__in=[ActivityLocationType.IN_PERSON, ActivityLocationType.HYBRID])
            for pk, gps in physical.values_list('pk', 'location_gps'):
                point = coordinates(gps)
                if point and any(lo <= distance_miles(origin, point) < hi for lo, hi in (DISTANCES[v] for v in buckets)):
                    ids.append(pk)
            condition |= Q(pk__in=ids)
        queryset = queryset.filter(condition)
    selections = params.getlist('cost')
    if selections:
        condition = Q(pk__in=[])
        tiers = {'1_10': (1, 10), '11_25': (11, 25), '26_50': (26, 50), '51_100': (51, 100), '100_plus': (100, None)}
        for value in selections:
            if value == 'free':
                condition |= Q(cost_type=value)
            else:
                low, high = tiers[value]
                tier = Q(cost_type='paid')
                tier &= Q(cost_amount__gt=low) if high is None else Q(cost_amount__gte=low)
                if high is not None:
                    tier &= Q(cost_amount__lte=high)
                condition |= tier
        queryset = queryset.filter(condition)
    if params.getlist('audience'):
        queryset = queryset.filter(audience__in=params.getlist('audience'))
    if params.get('location_notice') == 'unavailable':
        warning = 'Distance filters are off. Location access was denied or unavailable.'
    return queryset, nearby, warning
