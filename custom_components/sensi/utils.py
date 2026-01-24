"""Utils for Sensi integration."""

from __future__ import annotations

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


def to_bool(value: str | bool) -> bool:
    """Determine if a value is truthy."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    value_lower = value.lower()
    return value_lower in {"true", "yes", "on"}


def bool_to_onoff(value: bool) -> str:
    """Determine if a value is truthy."""
    return "on" if value else "off"
