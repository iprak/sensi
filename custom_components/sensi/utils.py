"""Utils for Sensi integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


def to_bool(value: str) -> bool:
    """Determine if a value is truthy."""
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
