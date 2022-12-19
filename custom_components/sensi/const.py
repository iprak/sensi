"""Constants for the Sensi Thermostat component."""

from typing import Final

SENSI_DOMAIN: Final = "sensi"
SENSI_NAME: Final = "Sensi Thermostat"
ATTRIBUTION: Final = "Data provided by Sensi"

SENSI_FAN_AUTO: Final = "auto"
SENSI_FAN_ON: Final = "on"
SENSI_FAN_CIRCULATE: Final = "Circulate"
FAN_CIRCULATE_DEFAULT_DUTY_CYCLE = 10


DOMAIN_DATA_COORDINATOR_KEY: Final = "coordinator"
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = SENSI_DOMAIN
