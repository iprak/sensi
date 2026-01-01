"""Constants for the Sensi Thermostat component."""

from __future__ import annotations

import logging
from typing import Final

CONFIG_REFRESH_TOKEN: Final = "refresh_token"

SENSI_DOMAIN: Final = "sensi"
SENSI_NAME: Final = "Sensi Thermostat"
SENSI_ATTRIBUTION: Final = "Data provided by Sensi"

SENSI_FAN_AUTO: Final = "auto"
SENSI_FAN_ON: Final = "on"
SENSI_FAN_CIRCULATE: Final = "Circulate"
FAN_CIRCULATE_DEFAULT_DUTY_CYCLE = 10


STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = SENSI_DOMAIN

# The Sensi app defines min/max values as 45 ad 99. We will use a slightly lower range as absolute range limits.
COOL_MIN_TEMPERATURE: Final = 50
HEAT_MAX_TEMPERATURE: Final = 95

# Min and max humidity levels as defined in the mobile app.
DEFAULT_MIN_HUMIDITY: Final = 5
DEFAULT_MAX_HUMIDITY: Final = 50

# Sensi only allows humidity to be changed in steps of 5 or else returns an error.
DEFAULT_HUMIDITY_STEP: Final = 5

LOGGER = logging.getLogger(__package__)

CONFIG_FAN_SUPPORT: Final = "fan_support"
DEFAULT_CONFIG_FAN_SUPPORT: Final = True

CONFIG_AUX_HEATING: Final = "aux_heat"

COORDINATOR_UPDATE_INTERVAL: Final = 30

ATTR_CIRCULATING_FAN: Final = "circulating_fan"
ATTR_CIRCULATING_FAN_DUTY_CYCLE: Final = "circulating_fan_duty_cycle"
ATTR_BATTERY_VOLTAGE: Final = "battery_voltage"
