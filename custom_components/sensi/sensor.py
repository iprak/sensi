"""Sensi thermostat sensors."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription, generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.sensi.coordinator import (
    SensiDevice,
    SensiEntity,
    SensiUpdateCoordinator,
)

from .const import DOMAIN_DATA_COORDINATOR_KEY, SENSI_DOMAIN

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS: Final = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi sensors."""
    data = hass.data[SENSI_DOMAIN][entry.entry_id]
    coordinator: SensiUpdateCoordinator = data[DOMAIN_DATA_COORDINATOR_KEY]

    entities = []
    for device in coordinator.get_devices():

        sub_entities = [
            SensiSensorEntity(device, description)
            for description in SENSOR_DESCRIPTIONS
        ]

        entities.extend(sub_entities)

    async_add_entities(entities)
    _LOGGER.info("Added %d sensors", len(entities))


class SensiSensorEntity(SensiEntity, SensorEntity):
    """Representation of a Sensi sensor."""

    # pylint: disable=too-many-instance-attributes
    # These attributes are okay.

    def __init__(
        self,
        device: SensiDevice,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, f"{device.identifier}_{description.key}")

        self._device = device
        self._name = f"{device.name} {description.name}"
        self.entity_description = description

        entity_id_format = description.key + ".{}"

        # Note: self.hass is not set at this point
        self.entity_id = generate_entity_id(
            entity_id_format,
            f"{SENSI_DOMAIN}_{self._name}",
            hass=device.coordinator.hass,
        )

        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = device.temperature_unit

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""

        return (
            self._device.temperature
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            else self._device.humidity
        )
