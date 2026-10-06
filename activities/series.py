"""Reusable values copied into an occurrence, never live inheritance."""
SERIES_DEFAULT_FIELDS = (
    'title', 'description', 'category', 'audience', 'available_responses',
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
        initial[name] = list(value) if isinstance(value, list) else value
    initial['group'] = series.group_id
    if not initial['header_image'] and series.group_id:
        initial['header_image'] = series.group.default_activity_image_id
    return initial
