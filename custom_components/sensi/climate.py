"""Sensi Thermostat."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import SensiEntity, get_fan_support
from .const import (
    DOMAIN_DATA_COORDINATOR_KEY,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    LOGGER,
    SENSI_DOMAIN,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
    SENSI_FAN_ON,
    Capabilities,
)
from .coordinator import SensiDevice, SensiUpdateCoordinator

FORCE_REFRESH_DELAY = 3


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

    # This is to suppress 'therefore implicitly supports the turn_on/turn_off methods
    # without setting the proper ClimateEntityFeature' warning
    _enable_turn_on_off_backwards_compatibility = False

    _retry_property_name: str
    _retry_expected_value: float | str | HVACMode
    _retry_callback: Callable[[float | str | HVACMode]]

    def __init__(self, device: SensiDevice, entry: ConfigEntry) -> None:
        """Initialize the device."""

        super().__init__(device)

        device.on_device_updated = self._on_device_updated
        self._retry_property_name = ""

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}",
            hass=device.coordinator.hass,
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
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

        return supported

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
            raise HomeAssistantError(f"The device {self._device.name} is offline.")

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        temperature = kwargs.get(ATTR_TEMPERATURE)

        temperature = round(temperature)

        # First invoke the setter operation. If it throws due to invalid value,
        # then retry doesn't need to be attempted.
        await self._async_set_temperature(temperature)
        self._register_retry(
            "target_temperature", temperature, self._async_set_temperature
        )

    async def _async_set_temperature(self, temperature: int) -> None:
        """Set new target temperature."""

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        if await self._device.async_set_temp(temperature):
            LOGGER.info("%s: Setting temperature to %d", self._device.name, temperature)
            self._force_refresh_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""

        if self._device.offline:
            raise HomeAssistantError(f"The device {self._device.name} is offline.")

        # First invoke the setter operation. If it throws due to invalid value,
        # then retry doesn't need to be attempted.
        await self._async_set_hvac_mode(hvac_mode)
        self._register_retry("hvac_mode", hvac_mode, self._async_set_hvac_mode)

    async def _async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""

        if await self._device.async_set_hvac_mode(hvac_mode):
            LOGGER.info("%s: Setting hvac_mode to %s", self._device.name, hvac_mode)
            self._force_refresh_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""

        if self._device.offline:
            raise HomeAssistantError(f"The device {self._device.name} is offline.")

        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        # First invoke the setter operation. If it throws due to invalid value,
        # then retry doesn't need to be attempted.
        await self._async_set_fan_mode(fan_mode)
        self._register_retry("fan_mode", fan_mode, self._async_set_fan_mode)

    async def _async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode.

        First set circulating fan mode state if the thermostat supports it
        and then update the fan mode.
        """

        success = False
        if fan_mode == SENSI_FAN_CIRCULATE:
            if await self._device.async_set_circulating_fan_mode(
                True, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
            ):
                success = await self._device.async_set_fan_mode(SENSI_FAN_AUTO)
        else:
            # Reset circulating fan mode state
            success = (
                await self._device.async_set_circulating_fan_mode(False, 0)
                if self._device.supports_circulating_fan_mode()
                else True
            )

            if success:
                success = await self._device.async_set_fan_mode(fan_mode)  # on or auto

        if success:
            self.async_write_ha_state()
            LOGGER.info("%s: Setting fan_mode to %s", self._device.name, fan_mode)

    async def async_turn_on(self) -> None:
        """Turn thermostat on."""

        if self._device.offline:
            raise HomeAssistantError(f"The device {self._device.name} is offline.")

        if await self._device.async_set_fan_mode(HVACMode.AUTO):
            self._force_refresh_state()

    def _force_refresh_state(self) -> None:
        """Force refresh after a delay."""

        # Write the current state and then force update
        self.async_write_ha_state()

        # Testing showed that update after a event request failed to bring new data.
        # Scheduing the next refresh after a delay.
        async_call_later(
            self.hass, FORCE_REFRESH_DELAY, self._async_force_refresh_state
        )

    async def _async_force_refresh_state(self, *_: Any) -> None:
        """Refresh the state."""
        await self.async_update()

    def _register_retry(
        self,
        property_name: str,
        expected_value: float | str | HVACMode,
        callback: Callable[[float | str | HVACMode]],
    ) -> None:
        """Save parameters to attempt retry if value did not update as expected."""
        self._retry_property_name = property_name
        self._retry_expected_value = expected_value
        self._retry_callback = callback

    def _on_device_updated(self) -> None:
        """Device state update callback."""
        asyncio.run_coroutine_threadsafe(
            self._async_on_device_updated(), self.hass.loop
        )

    async def _async_on_device_updated(self) -> None:
        """Device state update callback."""

        if self._retry_property_name:
            LOGGER.debug(
                "%s: Device state updated, checking if %s not matching",
                self._device.name,
                self._retry_property_name,
            )

            value = getattr(self, self._retry_property_name)
            if value != self._retry_expected_value:
                LOGGER.info(
                    "Current value for '%s' is '%s' and does not match the value set '%s', retrying",
                    self._retry_property_name,
                    value,
                    self._retry_expected_value,
                )

                # Reset _retry_property_name to prevent repeated operations
                self._retry_property_name = ""
                await self._retry_callback(self._retry_expected_value)
