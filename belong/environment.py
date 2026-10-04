"""Read local configuration without executing shell commands or needing dependencies."""

import shlex

CONFIG_KEYS = (
    "BELONG_ENV",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_DB_PATH",
    "DJANGO_SECRET_KEY",
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
        if not separator or key.strip() not in CONFIG_KEYS:
            raise ValueError(f"Invalid setting in {path.name}:{number}.")
        try:
            tokens = shlex.split(value, comments=True)
        except ValueError as error:
            raise ValueError(f"Invalid value in {path.name}:{number}.") from error
        if len(tokens) > 1:
            raise ValueError(f"Quote values containing spaces in {path.name}:{number}.")
        config[key.strip()] = tokens[0] if tokens else ""
    return config


def config_bool(value):
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("DJANGO_DEBUG must be a boolean (true or false).")
