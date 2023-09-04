"""Constants for the Sensi Thermostat component."""

from enum import StrEnum
import logging
from typing import Final

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


class DisplayProperties(StrEnum):
    """Thermostat Display properties."""

    CONTINUOUS_BACKLIGHT = "continuous_backlight"
    DISPLAY_HUMIDITY = "display_humidity"
    DISPLAY_TIME = "display_time"


COORDINATOR_DELAY_REFRESH_AFTER_UPDATE: Final = 10


class Capabilities(StrEnum):
    """Thermostat simple capabilites."""

    CONTINUOUS_BACKLIGHT = "continuous_backlight"
    DEGREES_FC = "degrees_fc"
    DISPLAY_HUMIDITY = "display_humidity"
    DISPLAY_TIME = "display_time"
    CIRCULATING_FAN = "circulating_fan"
    FAN_MODE_SETTINGS = "fan_mode_settings"


CAPABILITIES_VALUE_GETTER: Final = {
    Capabilities.CIRCULATING_FAN: lambda item: item and item.get("capable", "no"),
}
