"""Sensi Thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import SensiConfigEntry, get_fan_support
from .const import (
    COOL_MIN_TEMPERATURE,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    HEAT_MAX_TEMPERATURE,
    LOGGER,
    SENSI_DOMAIN,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
    SENSI_FAN_ON,
)
from .coordinator import SensiUpdateCoordinator
from .data import (
    FanMode,
    OperatingMode,
    SensiDevice,
    get_hvac_mode_from_operating_mode,
    get_operating_mode_from_hvac_mode,
)
from .entity import SensiEntity
from .utils import raise_if_error

FORCE_REFRESH_DELAY = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostats."""
    coordinator = entry.runtime_data
    devices = coordinator.get_devices()
    entities = [SensiThermostat(device, entry, coordinator) for device in devices]
    async_add_entities(entities)


class SensiThermostat(SensiEntity, ClimateEntity):
    """Representation of a Sensi thermostat."""

    # This is to suppress 'therefore implicitly supports the turn_on/turn_off methods
    # without setting the proper ClimateEntityFeature' warning
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        device: SensiDevice,
        entry: SensiConfigEntry,
        coordinator: SensiUpdateCoordinator,
    ) -> None:
        """Initialize the device."""

        hass = coordinator.hass
        super().__init__(device, coordinator)

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}",
            hass=hass,
        )

        self._attr_target_temperature_step = (
            PRECISION_HALVES
            if hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS
            else PRECISION_WHOLE
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {}

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
        capabilities = self._device.capabilities

        modes = []

        if capabilities.operating_mode_settings.off:
            modes.append(HVACMode.OFF)
        if capabilities.operating_mode_settings.heat:
            modes.append(HVACMode.HEAT)
        if capabilities.operating_mode_settings.cool:
            modes.append(HVACMode.COOL)
        if capabilities.operating_mode_settings.auto:
            modes.append(HVACMode.AUTO)

        return modes

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._state.fan_mode

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return get_hvac_mode_from_operating_mode(self._state.operating_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        operating_mode = self._state.operating_mode

        # AC0/AC1/HP1 state=off
        # operating_mode=off, current_operating_mode=off, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        if operating_mode == OperatingMode.OFF:
            return HVACAction.OFF

        # Treat Aux as Heating
        if operating_mode == OperatingMode.AUX:
            return HVACAction.HEATING

        # AC0
        #   state=heat, target temp higher
        #   operating_mode=heat, current_operating_mode=heat, demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1712407356}

        #   state=heat, target temp low Thermostat shows "Heat"
        #   operating_mode=heat, current_operating_mode=heat, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #   state=cool, target temp higher
        #   operating_mode=cool, current_operating_mode=cool, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'cool', 'last_start': None}

        # AC1
        #   state=heat, target temp higher
        #   operating_mode=heat, current_operating_mode=heat, demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1712407536}

        #   state=heat, target temp low Thermostat shows "Heat"
        #   operating_mode=heat, current_operating_mode=heat, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #   state=heat, target temp lower cooling
        #   operating_mode=cool, current_operating_mode=cool, demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1712407661}

        #   state=auto, current=70 target=68/66
        #   operating_mode=auto, current_operating_mode=auto_cool, demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1712407661}

        #   state=auto, current=70 target=72/70
        #   operating_mode=auto, current_operating_mode=auto_heat, demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1712407796}

        # HP1
        #   state=auto
        #   operating_mode=auto, current_operating_mode=auto_cool, demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1712406686}
        #   operating_mode=auto, current_operating_mode=auto_heat, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #   state=aux
        #   operating_mode=aux, current_operating_mode=aux, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #   state=heat
        #   operating_mode=heat, current_operating_mode=heat, demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1712407116}

        demand_status = self._state.demand_status

        if demand_status.heat > 0:
            return HVACAction.HEATING
        if demand_status.cool > 0:
            return HVACAction.COOLING

        return HVACAction.IDLE

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""

        if not get_fan_support(self._device, self._entry):
            return None

        return (
            [SENSI_FAN_AUTO, SENSI_FAN_ON, SENSI_FAN_CIRCULATE]
            if self._device.capabilities.circulating_fan.capable
            else [SENSI_FAN_AUTO, SENSI_FAN_ON]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._state.display_temp

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        scale = self._state.display_scale
        return (
            UnitOfTemperature.CELSIUS
            if scale.lower() == "c"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        hvac_action = self.hvac_action

        if hvac_action == HVACAction.OFF:
            return None

        state = self._state
        cool_target = state.current_cool_temp
        heat_target = state.current_heat_temp

        if hvac_action == HVACAction.HEATING:
            return heat_target
        if hvac_action == HVACAction.COOLING:
            return cool_target

        # HVACAction.IDLE
        last_action_heat = state.demand_status.last == "heat"
        return heat_target if last_action_heat else cool_target

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature. This gets used as the lower bounds in UI."""

        # Use the thermostat defined minimum temperature if not heating.
        if self.hvac_mode == HVACMode.HEAT:
            return TemperatureConverter.convert(
                COOL_MIN_TEMPERATURE,
                UnitOfTemperature.FAHRENHEIT,
                self.temperature_unit,
            )
        return self._state.cool_min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature. This gets used as the upper bounds in UI."""

        # Use the thermostat defined maximum temperature if not cooling.
        if self.hvac_mode == HVACMode.COOL:
            return TemperatureConverter.convert(
                HEAT_MAX_TEMPERATURE,
                UnitOfTemperature.FAHRENHEIT,
                self.temperature_unit,
            )

        return self._state.heat_max_temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        temperature = kwargs.get(ATTR_TEMPERATURE)

        temperature = round(temperature)
        (error, _) = await self.coordinator.client.async_set_temperature(
            self._device, temperature
        )
        raise_if_error(error, "temperature", temperature)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""

        operating_mode = get_operating_mode_from_hvac_mode(hvac_mode)

        if not operating_mode:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        (error, _) = await self.coordinator.client.async_set_operating_mode(
            self._device, operating_mode
        )
        raise_if_error(error, "operating mode", operating_mode.value)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""

        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        if fan_mode == SENSI_FAN_CIRCULATE:
            (
                error,
                _,
            ) = await self.coordinator.client.async_set_circulating_fan_mode(
                self._device, True, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
            )
            raise_if_error(
                error, "fan mode", f"{FAN_CIRCULATE_DEFAULT_DUTY_CYCLE} duty cycle"
            )
            await self.async_turn_on()
        else:
            # Reset circulating fan mode state
            (error, _) = (
                await self.coordinator.client.async_set_circulating_fan_mode(
                    self._device, False, 0
                )
                if self._device.capabilities.circulating_fan.capable
                else (None, None)
            )
            raise_if_error(error, "circulating fan mode", "False with duty cycle of 0")

            (error, _) = await self.coordinator.client.async_set_fan_mode(
                self._device, fan_mode
            )  # on or auto
            raise_if_error(error, "fan mode", fan_mode)

        self.async_write_ha_state()
        LOGGER.info("%s: Setting fan_mode to %s", self._device.name, fan_mode)

    async def async_turn_on(self) -> None:
        """Turn thermostat on."""

        await super().async_turn_on()

        (error, _) = await self.coordinator.client.async_set_fan_mode(
            self._device, FanMode.AUTO.value
        )
        raise_if_error(error, "fan mode", FanMode.AUTO.value)
        self.async_write_ha_state()
