"""Slice A: versioned configuration, separate from legacy response statuses.

Only navigation capabilities are executable here. Planned actions are vocabulary
for later slices, never selectable buttons or writes to ActivityResponse.
"""
from copy import deepcopy
from django.core.exceptions import ValidationError

CONFIG_VERSION = 1
PATTERNS = {
    'scheduled': ('Fixed / scheduled event', ('confirm_attendance', 'decline_attendance')),
    'immediate': ('Immediate activity', ('join_now',)),
    'planning': ('Tentative planning', ('answer_poll',)),
    'ongoing': ('Ongoing / recurring opportunity', ('request_enrollment',)),
    'registration': ('Registration', ('register',)),
    'inquiry': ('Open-ended social inquiry', ('request_contact',)),
    'none': ('No response required', ()),
}
NAVIGATION_ACTIONS = ('view_details', 'open_external')
CREATOR_PATTERN_CHOICES = [('', 'Response choices (current flow)'), ('none', 'No response required')]


def make_config(pattern, *, actions=None):
    config = {'version': CONFIG_VERSION, 'pattern': pattern,
              'actions': list(actions) if actions is not None else ['view_details']}
    validate_config(config)
    return deepcopy(config)


def validate_config(config):
    if config is None:
        return  # The sole compatibility sentinel: legacy behavior is unchanged.
    if not isinstance(config, dict) or set(config) != {'version', 'pattern', 'actions'}:
        raise ValidationError('Choose a valid participation configuration.')
    if type(config['version']) is not int or config['version'] != CONFIG_VERSION:
        raise ValidationError('Unsupported participation configuration version.')
    if not isinstance(config['pattern'], str) or config['pattern'] not in PATTERNS:
        raise ValidationError('Unknown participation pattern.')
    actions = config['actions']
    if not isinstance(actions, list) or any(not isinstance(action, str) or action not in NAVIGATION_ACTIONS for action in actions):
        raise ValidationError('Only Details and external navigation actions are available in this slice.')
    if len(actions) != len(set(actions)) or 'view_details' not in actions:
        raise ValidationError('Include Details once and do not repeat actions.')


def configured_pattern_label(config):
    try:
        validate_config(config)
    except ValidationError:
        return 'Details only'
    return PATTERNS[config['pattern']][0] if config is not None else 'Response choices (current flow)'


def navigation_allowed(config, action):
    if config is None:
        return True
    try:
        validate_config(config)
    except ValidationError:
        return False
    return action in config['actions']
