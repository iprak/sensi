"""Utils for Sensi integration."""

from homeassistant.helpers.typing import StateType


def to_int(value: StateType, default: int | None) -> int | None:
    """Convert a value to an integer, or return the default if not possible."""
    if isinstance(value, (int, float)):
        return int(value)

    return default


def to_float(value: StateType, default: float | None) -> float | None:
    """Convert a value to a float, or return the default if not possible."""
    if isinstance(value, (int, float)):
        return float(value)

    return default


def to_bool(value: StateType) -> bool:
    """Determine if a value is truthy."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        # The API is expected to send "on"/"yes" strings, but a numeric or
        # otherwise unexpected value must not raise.
        return bool(value)

    return value.lower() in {"true", "yes", "on"}


def bool_to_onoff(value: bool) -> str:
    """Determine if a value is truthy."""
    return "on" if value else "off"


def redact_token(value: str | None) -> str:
    """Return a token rendering that is safe to write to the log.

    Refresh and access tokens are bearer credentials for the account. Logging
    them verbatim leaks account control into any debug log that gets shared.
    """
    if not value:
        return "<missing>"

    return f"<redacted:...{value[-4:]}>"
