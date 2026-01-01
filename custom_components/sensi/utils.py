"""Utils for Sensi integration."""

from __future__ import annotations


def to_bool(value: str) -> bool:
    """Determine if a value is truthy."""
    return value == "true" or value.lower() == "yes" or value.lower() == "on"


def bool_to_onoff(value: bool) -> str:
    """Determine if a value is truthy."""
    return "on" if value else "off"
