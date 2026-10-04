"""Small, explicit pilot filters; no geospatial service or inferred cost prose."""
from datetime import datetime, time, timedelta
import math
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import ActivityCostType, ActivityLocationType

NEARBY_MILES = 25


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


def filter_activities(queryset, params):
    zone = ZoneInfo(settings.PILOT_TIME_ZONE)
    today = timezone.now().astimezone(zone).date()
    midnight = datetime.combine(today, time.min, tzinfo=zone)
    if params.get('today') == '1' or params.get('timing') == 'today':
        queryset = queryset.filter(starts_at__gte=midnight, starts_at__lt=midnight + timedelta(days=1))
    if params.get('timing') == 'upcoming':
        queryset = queryset.filter(starts_at__gte=timezone.now())
    elif params.get('timing') == 'dateless':
        queryset = queryset.filter(starts_at__isnull=True)
    if params.get('online') == '1':
        queryset = queryset.filter(location_type__in=[ActivityLocationType.ONLINE, ActivityLocationType.HYBRID])
    if params.get('location') in ActivityLocationType.values:
        queryset = queryset.filter(location_type=params['location'])
    if params.get('free') == '1':
        queryset = queryset.filter(cost_type=ActivityCostType.FREE)
    if params.get('cost') in ActivityCostType.values:
        queryset = queryset.filter(cost_type=params['cost'])
    warning = ''
    nearby = False
    if params.get('nearby') == '1':
        origin = coordinates(f"{params.get('lat', '')},{params.get('lon', '')}")
        if origin is None:
            warning = 'Nearby is off. Allow location access to use it.'
        else:
            nearby = True
            ids = [pk for pk, gps in queryset.values_list('pk', 'location_gps')
                   if (point := coordinates(gps)) is not None and distance_miles(origin, point) <= NEARBY_MILES]
            queryset = queryset.filter(pk__in=ids)
    return queryset, nearby, warning
