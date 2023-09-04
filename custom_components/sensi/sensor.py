"""Sensi thermostat sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.sensi import SensiDescriptionEntity
from custom_components.sensi.coordinator import SensiDevice, SensiUpdateCoordinator

from .const import DOMAIN_DATA_COORDINATOR_KEY, SENSI_DOMAIN


@dataclass
class SensiSensorEntityDescriptionMixin:
    """Mixin for Sensi thermostat sensor."""

    value_fn: Callable[[SensiDevice], StateType]


@dataclass
class SensiSensorEntityDescription(
    SensorEntityDescription, SensiSensorEntityDescriptionMixin
):
    """Representation of a Sensi thermostat sensor."""


SENSOR_TYPES: Final = (
    SensiSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
    SensiSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.humidity,
    ),
    SensiSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda device: device.battery_voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""
    data = hass.data[SENSI_DOMAIN][entry.entry_id]
    coordinator: SensiUpdateCoordinator = data[DOMAIN_DATA_COORDINATOR_KEY]

    entities = [
        SensiSensorEntity(device, description)
        for device in coordinator.get_devices()
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class SensiSensorEntity(SensiDescriptionEntity, SensorEntity):
    """Representation of a Sensi thermostat sensor."""

    entity_description: SensiSensorEntityDescription

    def __init__(
        self,
        device: SensiDevice,
        description: SensiSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, description)

        # Note: self.hass is not set at this point
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.identifier}_{description.key}",
            hass=device.coordinator.hass,
        )

        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = device.temperature_unit

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._device)
