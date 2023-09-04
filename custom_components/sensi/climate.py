"""Sensi Thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Union

from homeassistant.components.climate import (  # ClimateEntityDescription,
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.sensi import SensiEntity
from custom_components.sensi.const import (
    DOMAIN_DATA_COORDINATOR_KEY,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    LOGGER,
    SENSI_DOMAIN,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
    SENSI_FAN_ON,
    Capabilities,
)
from custom_components.sensi.coordinator import (
    HA_TO_SENSI_HVACMode,
    SensiDevice,
    SensiUpdateCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat."""
    data = hass.data[SENSI_DOMAIN][entry.entry_id]
    coordinator: SensiUpdateCoordinator = data[DOMAIN_DATA_COORDINATOR_KEY]
    entities = [SensiThermostat(device) for device in coordinator.get_devices()]
    async_add_entities(entities)
    LOGGER.info("Added %d thermostats", len(entities))


class SensiThermostat(SensiEntity, ClimateEntity):
    """Representation of a Sensi thermostat."""

    _attr_hvac_modes = [
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.OFF,
    ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, device: SensiDevice) -> None:
        """Initialize the device."""

        super().__init__(device)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.identifier}",
            hass=device.coordinator.hass,
        )

    @property
    def extra_state_attributes(self) -> Union[Mapping[str, Any], None]:
        """Return the state attributes."""
        return self._device.attributes

    @property
    def name(self) -> str:
        """Return the name of the entity.

        Returning None since this is the primary entity.
        https://developers.home-assistant.io/docs/core/entity/#entity-naming
        """

        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return (
            [SENSI_FAN_AUTO, SENSI_FAN_ON, SENSI_FAN_CIRCULATE]
            if self._device.supports(Capabilities.CIRCULATING_FAN)
            else [SENSI_FAN_AUTO, SENSI_FAN_ON]
        )

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._device.temperature_unit

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return (
            self._device.heat_target
            if self.hvac_mode == HVACMode.HEAT
            else self._device.cool_target
        )

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._device.humidity

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return hvac operation ie. heat, cool mode."""
        return self._device.hvac_mode

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._device.fan_mode

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self._device.async_set_temp(round(temp))
        self.async_write_ha_state()
        LOGGER.info("Set temperature to %d", temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operating mode."""
        if hvac_mode not in HA_TO_SENSI_HVACMode:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        await self._device.async_set_operating_mode(HA_TO_SENSI_HVACMode[hvac_mode])
        self.async_write_ha_state()
        LOGGER.info("Set hvac_mode to %s", hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        if fan_mode == SENSI_FAN_CIRCULATE:
            await self._device.async_set_circulating_fan_mode(
                True, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
            )
            await self._device.async_set_fan_mode(SENSI_FAN_AUTO)
        else:
            await self._device.async_set_circulating_fan_mode(False, 0)
            await self._device.async_set_fan_mode(fan_mode)  # on or auto

        self.async_write_ha_state()
        LOGGER.info("Set fan_mode to %s", fan_mode)

    async def async_turn_on(self) -> None:
        """Turn thermostat on."""
        await self._device.async_set_fan_mode(HVACMode.AUTO)
        self.async_write_ha_state()
