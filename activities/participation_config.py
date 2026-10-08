"""Versioned semantic actions, separate from navigation and stored intent labels."""
from copy import deepcopy
from django.core.exceptions import ValidationError

CONFIG_VERSION = 1
INTENT_VERSION = 2
POLL_VERSION = 3
ENROLLMENT_VERSION = 4
REGISTRATION_VERSION = 5
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
CREATOR_PATTERN_CHOICES = [('', 'Response choices (current flow)'),
    ('scheduled', 'Scheduled event (free, open attendance)'),
    ('immediate', 'Immediate activity (free, join now)'), ('none', 'No response required')]
INTENT_ACTIONS = {
    'scheduled': {
        'confirm_attendance': ('committed', "I'm coming", 'Going'),
        'decline_attendance': ('declined', "Can't make it", "Can't make it"),
    },
    'immediate': {'join_now': ('committed', 'Join now', 'Joining')},
}


def make_config(pattern, *, actions=None, version=CONFIG_VERSION):
    defaults = ['view_details'] + (list(INTENT_ACTIONS.get(pattern, {})) if version == INTENT_VERSION else ['answer_poll'] if version == POLL_VERSION else ['request_enrollment'] if version == ENROLLMENT_VERSION else ['register'] if version == REGISTRATION_VERSION else [])
    config = {'version': version, 'pattern': pattern,
              'actions': list(actions) if actions is not None else defaults}
    validate_config(config)
    return deepcopy(config)


def validate_config(config):
    if config is None:
        return  # The sole compatibility sentinel: legacy behavior is unchanged.
    if not isinstance(config, dict) or set(config) != {'version', 'pattern', 'actions'}:
        raise ValidationError('Choose a valid participation configuration.')
    if type(config['version']) is not int or config['version'] not in (CONFIG_VERSION, INTENT_VERSION, POLL_VERSION, ENROLLMENT_VERSION, REGISTRATION_VERSION):
        raise ValidationError('Unsupported participation configuration version.')
    if not isinstance(config['pattern'], str) or config['pattern'] not in PATTERNS:
        raise ValidationError('Unknown participation pattern.')
    actions = config['actions']
    required = INTENT_ACTIONS.get(config['pattern'], {}) if config['version'] == INTENT_VERSION else {}
    if config['version'] == POLL_VERSION:
        if config['pattern'] != 'planning':
            raise ValidationError('Date polling requires the planning pattern.')
        required = {'answer_poll': None}
    if config['version'] == ENROLLMENT_VERSION:
        if config['pattern'] != 'ongoing':
            raise ValidationError('Free enrollment requires the ongoing pattern.')
        required = {'request_enrollment': None}
    if config['version'] == REGISTRATION_VERSION:
        if config['pattern'] != 'registration':
            raise ValidationError('Registration requires the registration pattern.')
        required = {'register': None}
    if config['version'] == INTENT_VERSION and not required:
        raise ValidationError('This version supports only scheduled/free and immediate participation.')
    allowed = (*NAVIGATION_ACTIONS, *required)
    if not isinstance(actions, list) or any(not isinstance(action, str) or action not in allowed for action in actions):
        raise ValidationError('Choose only supported actions for this pattern and version.')
    if len(actions) != len(set(actions)) or 'view_details' not in actions:
        raise ValidationError('Include Details once and do not repeat actions.')
    if not set(required).issubset(actions):
        raise ValidationError('Include the participation actions required by this pattern.')


def intent_options(config):
    try:
        validate_config(config)
    except ValidationError:
        return []
    if config is None or config['version'] != INTENT_VERSION:
        return []
    meanings = INTENT_ACTIONS[config['pattern']]
    return [{'field': 'action', 'value': action, 'status': meanings[action][0],
             'label': meanings[action][1], 'state_label': meanings[action][2]}
            for action in config['actions'] if action in meanings]


def is_date_planning(config):
    try:
        validate_config(config)
    except ValidationError:
        return False
    return config is not None and config['version'] == POLL_VERSION


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


def is_free_ongoing(config):
    try:
        validate_config(config)
    except ValidationError:
        return False
    return config is not None and config['version'] == ENROLLMENT_VERSION


def is_registration(config):
    try:
        validate_config(config)
    except ValidationError:
        return False
    return config is not None and config['version'] == REGISTRATION_VERSION
