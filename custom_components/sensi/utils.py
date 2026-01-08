"""Utils for Sensi integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import StateType


def to_int(value: StateType, default: int) -> int:
    """Convert a value to an integer, or return the default if not possible."""
    if isinstance(value, (int, float)):
        return int(value)

    return default


def to_float(value: StateType, default: float) -> float:
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
    return value == "true" or value.lower() == "yes" or value.lower() == "on"


def bool_to_onoff(value: bool) -> str:
    """Determine if a value is truthy."""
    return "on" if value else "off"


def raise_if_error(error: any, property: str, value: any) -> None:
    """Raise HomeAssistantError if error is defined.

    The exception is raised with the message `Unable to set {property} to {value}. {error}`.
    """
    if error:
        raise HomeAssistantError(f"Unable to set {property} to {value}. {error}")
