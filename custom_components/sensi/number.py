"""Sensi thermostat numeric settings."""

from __future__ import annotations

from typing import Final

from homeassistant.components.number import (
    ENTITY_ID_FORMAT,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import raise_if_error
from .const import SENSI_DOMAIN, TEMPERATURE_LOWER_LIMIT, TEMPERATURE_UPPER_LIMIT
from .coordinator import SensiConfigEntry, SensiDevice, SensiUpdateCoordinator
from .data import OperatingMode, State
from .entity import SensiDescriptionEntity

STEP: Final = 1


def get_state(device: SensiDevice) -> State:
    """Return the state of the device. This provides typing."""
    return device.state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat numbers."""
    coordinator = entry.runtime_data
    entities = []

    heat_description = NumberEntityDescription(
        device_class=NumberDeviceClass.TEMPERATURE,
        key="auto-current_heat_temp",
        name="Heat setpoint",
        step=STEP,
    )
    cool_description = NumberEntityDescription(
        device_class=NumberDeviceClass.TEMPERATURE,
        key="auto-current_cool_temp",
        name="Cool setpoint",
        step=STEP,
    )

    for device in coordinator.get_devices():
        entities.extend(
            [
                SensiHeatCoolNumberEntity(
                    hass, device, heat_description, coordinator, True
                ),
                SensiHeatCoolNumberEntity(
                    hass, device, cool_description, coordinator, False
                ),
            ]
        )

    async_add_entities(entities)


class SensiHeatCoolNumberEntity(SensiDescriptionEntity, NumberEntity):
    """Representation of a Sensi number entity."""

    entity_description: NumberEntityDescription = None

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        description: NumberEntityDescription,
        coordinator: SensiUpdateCoordinator,
        heat: bool,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, description, coordinator)

        self._heat = heat  # Tracking the heat temperature

        # Note: self.hass is not set at this point
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=hass,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        mode = self._device.state.operating_mode

        # Temperatures cannot be set if device is OFF
        if mode == OperatingMode.OFF:
            return False

        if (self._heat and mode in [OperatingMode.AUTO, OperatingMode.HEAT]) or (
            not self._heat
            and mode
            in [
                OperatingMode.AUTO,
                OperatingMode.COOL,
            ]
        ):
            return super().available

        return False

    @property
    def native_value(self) -> float:
        """Return the value reported by the entity."""
        return (
            self._device.state.current_heat_temp
            if self._heat
            else self._device.state.current_cool_temp
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of the entity, if any."""
        return self._device.state.temperature_unit

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""

        response = await self.coordinator.client.async_set_temperature(
            self._device,
            OperatingMode.HEAT if self._heat else OperatingMode.COOL,
            value,
        )
        raise_if_error(response, self.entity_description.name, value)
        self.async_write_ha_state()

        # Force entities using the same value to refresh
        self.coordinator.async_update_listeners()

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return (
            TEMPERATURE_LOWER_LIMIT
            if self._heat
            else self._device.state.current_heat_temp + 1
        )

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return (
            self._device.state.current_cool_temp - 1
            if self._heat
            else TEMPERATURE_UPPER_LIMIT
        )
