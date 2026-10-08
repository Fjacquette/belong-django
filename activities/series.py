"""Reusable values copied into an occurrence, never live inheritance."""
from copy import deepcopy
SERIES_DEFAULT_FIELDS = (
    'title', 'description', 'category', 'audience', 'participation_config', 'available_responses', 'invite_group_members',
    'location_type', 'location_name', 'location_address1', 'location_address2',
    'location_city', 'location_state', 'location_zip', 'location_url',
    'location_gps', 'location_instructions', 'cost_type', 'cost_amount',
    'cost_display', 'header_image', 'color_primary', 'color_secondary',
)


def occurrence_initial(series):
    initial = {}
    for name in SERIES_DEFAULT_FIELDS:
        field = series._meta.get_field(name)
        value = getattr(series, field.attname)
        initial[name] = deepcopy(value)
    initial['group'] = series.group_id
    from .models import current_response_values, DEFAULT_RESPONSE_CHOICES
    initial['available_responses'] = (current_response_values(series.available_responses) or list(DEFAULT_RESPONSE_CHOICES)) if series.uses_legacy_participation else []
    initial['participation_pattern'] = series.participation_config['pattern'] if series.participation_config else ''
    if not initial['header_image'] and series.group_id:
        initial['header_image'] = series.group.default_activity_image_id
    return initial
