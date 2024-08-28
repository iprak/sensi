"""Sensi thermostat sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SensiDescriptionEntity
from .const import DOMAIN_DATA_COORDINATOR_KEY, SENSI_DOMAIN, Settings
from .coordinator import SensiDevice, SensiUpdateCoordinator


@dataclass(frozen=True)
class SensiSensorEntityDescription(SensorEntityDescription):
    """Representation of a Sensi thermostat sensor."""

    extra_state_attributes_fn: Callable[[Any], dict[str, str]] | None = None
    value_fn: Callable[[SensiDevice], StateType] = None


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
        return (
            self.entity_description.value_fn(self._device)
            if self.entity_description.value_fn
            else None
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return (
            self._device.temperature_unit
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        return (
            self.entity_description.extra_state_attributes_fn(self._device)
            if self.entity_description.extra_state_attributes_fn
            else None
        )
