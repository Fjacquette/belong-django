"""Read local configuration without executing shell commands or needing dependencies."""

import shlex

CONFIG_KEYS = (
    "BELONG_ENV",
    "BELONG_BETA_MODE",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_DB_PATH",
    "DJANGO_SECRET_KEY",
    "DJANGO_EMAIL_BACKEND",
    "DJANGO_DEFAULT_FROM_EMAIL",
    "BELONG_ALLOW_LEGACY_ACCOUNTS",
    "BELONG_PUBLIC_ORIGIN",
)


def read_local_config(path):
    if not path.exists():
        return {}
    config = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        error_key = (key.strip().split() or ['<missing key>'])[0]
        if not separator or key.strip() not in CONFIG_KEYS:
            raise ValueError(f"Invalid setting {error_key!r} in {path.name}:{number}.")
        try:
            tokens = shlex.split(value, comments=True)
        except ValueError as error:
            raise ValueError(f"Invalid value for {key.strip()} in {path.name}:{number}.") from error
        if len(tokens) > 1:
            raise ValueError(f"Quote values containing spaces for {key.strip()} in {path.name}:{number}.")
        config[key.strip()] = tokens[0] if tokens else ""
    return config


def config_bool(value, key="DJANGO_DEBUG"):
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean (true or false).")
