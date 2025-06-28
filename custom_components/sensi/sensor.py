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
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SensiDescriptionEntity
from .const import SENSI_DOMAIN, Settings
from .coordinator import SensiConfigEntry, SensiDevice, SensiUpdateCoordinator


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
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
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
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.battery_level,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensiSensorEntityDescription(
        key=Settings.COOL_MIN_TEMP,
        name="Min setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.min_temp,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensiSensorEntityDescription(
        key=Settings.HEAT_MAX_TEMP,
        name="Max setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.max_temp,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""
    coordinator: SensiUpdateCoordinator = entry.runtime_data.coordinator

    entities = [
        SensiSensorEntity(device, description)
        for device in coordinator.get_devices()
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class SensiSensorEntity(SensiDescriptionEntity, SensorEntity):
    """Representation of a Sensi thermostat sensor."""

    entity_description: SensiSensorEntityDescription = None

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
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=device.coordinator.hass,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return self._device.temperature_unit

        return self.entity_description.native_unit_of_measurement
