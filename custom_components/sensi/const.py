"""Constants for the Sensi Thermostat component."""
from __future__ import annotations

from enum import StrEnum
import logging
from typing import Final

from homeassistant.components.climate import HVACMode

SENSI_DOMAIN: Final = "sensi"
SENSI_NAME: Final = "Sensi Thermostat"
SENSI_ATTRIBUTION: Final = "Data provided by Sensi"

SENSI_FAN_AUTO: Final = "auto"
SENSI_FAN_ON: Final = "on"
SENSI_FAN_CIRCULATE: Final = "Circulate"
FAN_CIRCULATE_DEFAULT_DUTY_CYCLE = 10


DOMAIN_DATA_COORDINATOR_KEY: Final = "coordinator"
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = SENSI_DOMAIN

COOL_MIN_TEMPERATURE: Final = 45
HEAT_MAX_TEMPERATURE: Final = 99

LOGGER = logging.getLogger(__package__)

CONFIG_FAN_SUPPORT: Final = "fan_support"
DEFAULT_FAN_SUPPORT: Final = True

COORDINATOR_DELAY_REFRESH_AFTER_UPDATE: Final = 10
COORDINATOR_UPDATE_INTERVAL: Final = 30

ATTR_CIRCULATING_FAN: Final = "circulating_fan"
ATTR_CIRCULATING_FAN_DUTY_CYCLE: Final = "circulating_fan_duty_cycle"
ATTR_OFFLINE: Final = "offline"
ATTR_POWER_STATUS: Final = "power_status"
ATTR_WIFI_QUALITY: Final = "wifi_connection_quality"
ATTR_BATTERY_VOLTAGE: Final = "battery_voltage"

class Settings(StrEnum):
    """Thermostat Display properties."""

    CONTINUOUS_BACKLIGHT = "continuous_backlight"
    DISPLAY_HUMIDITY = "display_humidity"
    DISPLAY_TIME = "display_time"


class OperatingModes(StrEnum):
    """Thermostat operating mode values. This is based on OperatingMode (OperatingMode.java)."""

    OFF = "off"
    AUX = "aux"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"


class Capabilities(StrEnum):
    """Thermostat simple capabilites."""

    CONTINUOUS_BACKLIGHT = "continuous_backlight"
    DEGREES_FC = "degrees_fc"
    DISPLAY_HUMIDITY = "display_humidity"
    DISPLAY_TIME = "display_time"
    CIRCULATING_FAN = "circulating_fan"
    FAN_MODE_AUTO = "fan_mode_settings.auto"
    FAN_MODE_ON = "fan_mode_settings.on"
    OPERATING_MODE_OFF = "operating_mode_settings.off"
    OPERATING_MODE_HEAT = "operating_mode_settings.heat"
    OPERATING_MODE_COOL = "operating_mode_settings.cool"
    OPERATING_MODE_AUTO = "operating_mode_settings.auto"
    OPERATING_MODE_AUX = "operating_mode_settings.aux"


CAPABILITIES_VALUE_GETTER: Final = {
    # circulating_fan
    Capabilities.CIRCULATING_FAN: lambda item: item and item.get("capable", "no"),
    # fan_mode_settings
    Capabilities.FAN_MODE_AUTO: lambda item: item and item.get("auto", "no"),
    Capabilities.FAN_MODE_ON: lambda item: item and item.get("on", "no"),
    # operating_mode_settings
    Capabilities.OPERATING_MODE_OFF: lambda item: item and item.get("off", "no"),
    Capabilities.OPERATING_MODE_HEAT: lambda item: item and item.get("heat", "no"),
    Capabilities.OPERATING_MODE_COOL: lambda item: item and item.get("cool", "no"),
    Capabilities.OPERATING_MODE_AUTO: lambda item: item and item.get("auto", "no"),
    Capabilities.OPERATING_MODE_AUX: lambda item: item and item.get("aux", "no"),
}

OPERATING_MODE_TO_HVAC_MODE = {
    OperatingModes.AUX: HVACMode.HEAT,
    OperatingModes.HEAT: HVACMode.HEAT,
    OperatingModes.COOL: HVACMode.COOL,
    OperatingModes.AUTO: HVACMode.AUTO,
    OperatingModes.OFF: HVACMode.OFF,
}

HVAC_MODE_TO_OPERATING_MODE = {
    HVACMode.HEAT: OperatingModes.HEAT,
    HVACMode.COOL: OperatingModes.COOL,
    HVACMode.AUTO: OperatingModes.AUTO,
    HVACMode.OFF: OperatingModes.OFF,
}
