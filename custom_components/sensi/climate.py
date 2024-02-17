"""Sensi Thermostat."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Union

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SensiEntity, get_fan_support
from .const import (
    DOMAIN_DATA_COORDINATOR_KEY,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    HVAC_MODE_TO_OPERATING_MODE,
    LOGGER,
    SENSI_DOMAIN,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
    SENSI_FAN_ON,
    Capabilities,
    OperatingModes,
)
from .coordinator import SensiDevice, SensiUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat."""
    data = hass.data[SENSI_DOMAIN][entry.entry_id]
    coordinator: SensiUpdateCoordinator = data[DOMAIN_DATA_COORDINATOR_KEY]
    entities = [SensiThermostat(device, entry) for device in coordinator.get_devices()]
    async_add_entities(entities)


class SensiThermostat(SensiEntity, ClimateEntity):
    """Representation of a Sensi thermostat."""

    _attr_target_temperature_step = PRECISION_WHOLE
    _last_hvac_mode_before_aux_heat: HVACMode | str | None

    # This is to suppress 'therefore implicitly supports the turn_on/turn_off methods
    # without setting the proper ClimateEntityFeature' warning
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, device: SensiDevice, entry: ConfigEntry) -> None:
        """Initialize the device."""

        super().__init__(device)

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}",
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
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""

        supported = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        if get_fan_support(self._device, self._entry):
            supported = supported | ClimateEntityFeature.FAN_MODE

        if self._device.supports(Capabilities.OPERATING_MODE_AUX):
            supported = supported | ClimateEntityFeature.AUX_HEAT

        return supported

    @property
    def is_aux_heat(self) -> bool:
        """Return true if aux heater is enabled."""
        return self._device.effective_operating_mode == OperatingModes.AUX

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""

        modes = []

        if self._device.supports(Capabilities.OPERATING_MODE_OFF):
            modes.append(HVACMode.OFF)
        if self._device.supports(Capabilities.OPERATING_MODE_HEAT):
            modes.append(HVACMode.HEAT)
        if self._device.supports(Capabilities.OPERATING_MODE_COOL):
            modes.append(HVACMode.COOL)
        if self._device.supports(Capabilities.OPERATING_MODE_AUTO):
            modes.append(HVACMode.AUTO)

        return modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        return self._device.hvac_action

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""

        if not get_fan_support(self._device, self._entry):
            return None

        return (
            [SENSI_FAN_AUTO, SENSI_FAN_ON, SENSI_FAN_CIRCULATE]
            if self._device.supports(Capabilities.CIRCULATING_FAN)
            else [SENSI_FAN_AUTO, SENSI_FAN_ON]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return self._device.temperature_unit

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

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

        if self._device.offline:
            LOGGER.info("%s: device is offline", self._device.name)
            return

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self._device.async_set_temp(round(temp))
        self.async_write_ha_state()
        LOGGER.info("Set temperature to %d", temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operating mode."""

        if self._device.offline:
            LOGGER.info("%s: device is offline", self._device.name)
            return

        if hvac_mode not in HVAC_MODE_TO_OPERATING_MODE:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        if await self._device.async_set_operating_mode(
            HVAC_MODE_TO_OPERATING_MODE[hvac_mode]
        ):
            self.async_write_ha_state()
            LOGGER.info("%s: hvac_mode set to %s", self._device.name, hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""

        if self._device.offline:
            LOGGER.info("%s: device is offline", self._device.name)
            return

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
        LOGGER.info("%s: set fan_mode to %s", self._device.name, fan_mode)

    async def async_turn_on(self) -> None:
        """Turn thermostat on."""

        if self._device.offline:
            LOGGER.info("%s: device is offline", self._device.name)
            return

        await self._device.async_set_fan_mode(HVACMode.AUTO)
        self.async_write_ha_state()

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""

        if self._device.offline:
            LOGGER.info("%s: device is offline", self._device.name)
            return

        self._last_hvac_mode_before_aux_heat = self.hvac_mode

        if await self._device.async_enable_aux_mode():
            self.async_write_ha_state()

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        await self.async_set_hvac_mode(self._last_hvac_mode_before_aux_heat)
