"""Sensi thermostat numeric settings."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.number import (
    ENTITY_ID_FORMAT,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import ActionResponse, SensiClient, raise_if_error
from .const import SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiDevice
from .data import State
from .entity import SensiDescriptionEntity

MINIMUM_HUMIDITY_OFFSET: Final = -25
MAXIMUM_HUMIDITY_OFFSET: Final = 25

MINIMUM_TEMPERATURE_OFFSET: Final = -5
MAXIMUM_TEMPERATURE_OFFSET: Final = 5

STEP: Final = 1


def get_state(device: SensiDevice) -> State:
    """Return the state of the device. This provides typing."""
    return device.state


@dataclass(frozen=True, kw_only=True)
class SensiNumberEntityDescription(NumberEntityDescription):
    """Representation of a Sensi thermostat numeric setting."""

    update_fn: Callable[
        [SensiClient, SensiDevice, int], Coroutine[Any, Any, ActionResponse]
    ]
    value_fn: Callable[[SensiDevice], int | None]


NUMBER_TYPES: Final = [
    SensiNumberEntityDescription(
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        key="temperature_offset",
        name="Temperature offset",
        native_max_value=MAXIMUM_TEMPERATURE_OFFSET,
        native_min_value=MINIMUM_TEMPERATURE_OFFSET,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        step=STEP,
        update_fn=lambda client, device, value: client.async_set_temperature_offset(
            device, value
        ),
        value_fn=lambda device: get_state(device).temp_offset,
    ),
    SensiNumberEntityDescription(
        device_class=NumberDeviceClass.HUMIDITY,
        entity_category=EntityCategory.CONFIG,
        key="humidity_offset",
        name="Humidity offset",
        native_max_value=MAXIMUM_HUMIDITY_OFFSET,
        native_min_value=MINIMUM_HUMIDITY_OFFSET,
        native_unit_of_measurement=PERCENTAGE,
        step=STEP,
        update_fn=lambda client, device, value: client.async_set_humidity_offset(
            device, value
        ),
        value_fn=lambda device: get_state(device).humidity_offset,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat numbers."""
    coordinator = entry.runtime_data

    entities = [
        SensiNumberEntity(hass, device, description, entry)
        for device in coordinator.get_devices()
        for description in NUMBER_TYPES
    ]

    async_add_entities(entities)


class SensiNumberEntity(SensiDescriptionEntity, NumberEntity):
    """Representation of a Sensi number entity."""

    entity_description: SensiNumberEntityDescription = None

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        description: SensiNumberEntityDescription,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, description, entry)

        # Note: self.hass is not set at this point
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=hass,
        )

    @property
    def native_value(self) -> float:
        """Return the value reported by the entity."""
        return self.entity_description.value_fn(self._device)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of the entity, if any."""
        return (
            self._state.temperature_unit
            if self.entity_description.device_class == NumberDeviceClass.TEMPERATURE
            else self.entity_description.native_unit_of_measurement
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        response = await self.entity_description.update_fn(
            self.coordinator.client, self._device, int(value)
        )
        raise_if_error(response, self.entity_description.name, value)
        self.async_write_ha_state()

        # Force data update since offsets control the thermostat state
        await self.coordinator.async_refresh()
