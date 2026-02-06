"""Sensi Thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import SensiConfigEntry, get_config_option
from .client import raise_if_error
from .const import (
    ATTR_CIRCULATING_FAN,
    ATTR_CIRCULATING_FAN_DUTY_CYCLE,
    ATTR_POWER_STATUS,
    CONFIG_FAN_SUPPORT,
    DEFAULT_CONFIG_FAN_SUPPORT,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    LOGGER,
    SENSI_DOMAIN,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
    SENSI_FAN_ON,
    TEMPERATURE_LOWER_LIMIT,
    TEMPERATURE_UPPER_LIMIT,
)
from .data import (
    FanMode,
    OperatingMode,
    SensiDevice,
    get_hvac_mode_from_operating_mode,
    get_operating_mode_from_hvac_mode,
)
from .entity import SensiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostats."""
    coordinator = entry.runtime_data
    devices = coordinator.get_devices()
    entities = [SensiThermostat(hass, device, entry) for device in devices]
    async_add_entities(entities)


class SensiThermostat(SensiEntity, ClimateEntity):
    """Representation of a Sensi thermostat."""

    # This is to suppress 'therefore implicitly supports the turn_on/turn_off methods
    # without setting the proper ClimateEntityFeature' warning
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the device."""

        super().__init__(device, entry)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}",
            hass=hass,
        )

        # The mobile device always uses whole numbers for C and F unit
        self._attr_target_temperature_step = PRECISION_WHOLE

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            ATTR_CIRCULATING_FAN: self._state.circulating_fan.enabled,
            ATTR_CIRCULATING_FAN_DUTY_CYCLE: self._state.circulating_fan.duty_cycle,
            ATTR_POWER_STATUS: self._state.power_status,
        }

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

        supported = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

        if get_config_option(
            self._device, self._entry, CONFIG_FAN_SUPPORT, DEFAULT_CONFIG_FAN_SUPPORT
        ):
            supported = supported | ClimateEntityFeature.FAN_MODE

        # If device is humidification capable (has something in humidification) and humidification is enabled
        if (
            self._device.capabilities.humidity_control.humidification
            and self._state.humidity_control.humidification.enabled
        ):
            supported = supported | ClimateEntityFeature.TARGET_HUMIDITY

        return supported | (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            if self._state.operating_mode == OperatingMode.AUTO
            else ClimateEntityFeature.TARGET_TEMPERATURE
        )

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

        # Create a special mode 'circulate' base on 'auto' when 'circulating_fan' contains 'enabled'='on'.
        if self._state.fan_mode == FanMode.AUTO and self._state.circulating_fan.enabled:
            return SENSI_FAN_CIRCULATE

        return self._state.fan_mode.value

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return get_hvac_mode_from_operating_mode(self._state.operating_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""

        # [Aux mode]
        #     Off
        #     operating_mode=current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #     Heat
        #     operating_mode=current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706456258}

        #     Cool
        #     operating_mode=current_operating_mode=cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706456358}

        #     Aux
        #     operating_mode=current_operating_mode=aux
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': 1, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 100, 'last': 'heat', 'last_start': 1706456438}

        # [Off]
        #     Off
        #     operating_mode=off, current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        # [Heat]
        #     Heating:
        #     operating_mode=heat, current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706461614}

        #     Heating (multistage) where heat can be 50:
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 50, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706461614}

        #     idle:
        #     operating_mode=heat, current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        # [Cool]
        #     Idle:
        #     operating_mode=off, current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'cool', 'last_start': None}

        #     Cooling:
        #     operating_mode=cool, current_operating_mode=cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706461689}

        # [Auto]
        #     cooling:
        #     operating_mode=auto, current_operating_mode=auto_cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706462094}

        #     idle:
        #     operating_mode=auto, current_operating_mode=auto_heat
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #     heating
        #     operating_mode=auto, current_operating_mode=auto_heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706462635}

        # When thermostat is set to Off, operating_mode and current_operating_mode are both Off. Themostat should not be be demanding heating or cooling.

        operating_mode = self._state.operating_mode

        # AC0/AC1/HP1 state=off
        # operating_mode=off, current_operating_mode=off, demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        if operating_mode == OperatingMode.OFF:
            return HVACAction.OFF

        # Treat Aux as Heating
        if operating_mode == OperatingMode.AUX:
            return HVACAction.HEATING

        # https://sensi.copeland.com/en-us/support/how-do-i-configure-my-thermostat
        # HP1 = heat pump
        # AC0 = no cooling
        # AC1 =  air conditioning uni
        # HP2/AC2 = more than one stage cooling/heating

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

        if not get_config_option(
            self._device, self._entry, CONFIG_FAN_SUPPORT, DEFAULT_CONFIG_FAN_SUPPORT
        ):
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
        return self._state.temperature_unit.value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""

        state = self._state

        if state.operating_mode == OperatingMode.OFF:
            return None

        cool_target = state.current_cool_temp
        heat_target = state.current_heat_temp

        if state.operating_mode == OperatingMode.HEAT:
            return heat_target
        if state.operating_mode == OperatingMode.COOL:
            return cool_target

        # For other modes use the last demand_status
        last_action_heat = state.demand_status.last == "heat"
        return heat_target if last_action_heat else cool_target

    @property
    def target_temperature_high(self) -> float:
        """Return the highbound target temperature we try to reach."""
        return self._state.current_cool_temp

    @property
    def target_temperature_low(self) -> float:
        """Return the lowbound target temperature we try to reach."""
        return self._state.current_heat_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature for single mode. This gets used as the lower bounds in UI."""

        # Use the thermostat defined minimum temperature if not heating. This is in temperature_unit.
        if self._state.operating_mode == OperatingMode.COOL:
            return self._state.cool_min_temp

        return TemperatureConverter.convert(
            TEMPERATURE_LOWER_LIMIT,
            UnitOfTemperature.FAHRENHEIT,
            self.temperature_unit,
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature for single mode. This gets used as the upper bounds in UI."""

        # Use the thermostat defined maximum temperature if not cooling. This is in temperature_unit.
        if self._state.operating_mode == OperatingMode.HEAT:
            return self._state.heat_max_temp

        return TemperatureConverter.convert(
            TEMPERATURE_UPPER_LIMIT,
            UnitOfTemperature.FAHRENHEIT,
            self.temperature_unit,
        )

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._state.humidity

    @property
    def target_humidity(self) -> float | None:
        """Return the humidity we try to reach."""
        if self._device.capabilities.humidity_control.humidification is None:
            return None

        humidification = self._state.humidity_control.humidification
        if humidification is None:
            return None
        return humidification.target_percent if humidification.enabled else None

    @property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""
        if self._device.capabilities.humidity_control.humidification is None:
            return None

        humidification = self._state.humidity_control.humidification
        if humidification is None or not humidification.enabled:
            return None

        return self._device.capabilities.humidity_control.humidification.min

    @property
    def max_humidity(self) -> float:
        """Return the maximum humidity."""
        if self._device.capabilities.humidity_control.humidification is None:
            return None

        humidification = self._state.humidity_control.humidification
        if humidification is None or not humidification.enabled:
            return None

        return self._device.capabilities.humidity_control.humidification.max

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""

        state = self._state

        # The framework ensures that the temperatures are within min_temp and max_temp.

        # ATTR_TEMPERATURE => ClimateEntityFeature.TARGET_TEMPERATURE
        # ATTR_TARGET_TEMP_LOW/ATTR_TARGET_TEMP_HIGH => TARGET_TEMPERATURE_RANGE
        if state.operating_mode == OperatingMode.AUTO:
            temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

            response = await self.coordinator.client.async_set_temperature(
                self._device, OperatingMode.HEAT, temperature_low
            )
            raise_if_error(response, "Heat setpoint", temperature_low)

            response = await self.coordinator.client.async_set_temperature(
                self._device, OperatingMode.COOL, temperature_high
            )
            raise_if_error(response, "Cool setpoint", temperature_high)
        else:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            response = await self.coordinator.client.async_set_temperature(
                self._device, state.operating_mode, temperature
            )

            raise_if_error(response, "temperature", temperature)

        self.async_write_ha_state()

        # Refresh entities relying on temperatures
        self.coordinator.async_update_listeners()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""

        operating_mode = get_operating_mode_from_hvac_mode(hvac_mode)

        if not operating_mode:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        response = await self.coordinator.client.async_set_operating_mode(
            self._device, operating_mode
        )
        raise_if_error(response, "operating mode", operating_mode.value)
        self.async_write_ha_state()

        # Refresh entities relying on operating_mode
        self.coordinator.async_update_listeners()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""

        # Valid fan_modes are  (SENSI_FAN_AUTO, SENSI_FAN_ON, SENSI_FAN_CIRCULATE)
        # or (SENSI_FAN_AUTO, SENSI_FAN_ON)
        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        if fan_mode == SENSI_FAN_CIRCULATE:
            # First set fan_mode to auto
            response = await self.coordinator.client.async_set_fan_mode(
                self._device, SENSI_FAN_AUTO
            )
            raise_if_error(response, "fan mode", fan_mode)

            # Next enable the circulating fan state
            response = await self.coordinator.client.async_set_circulating_fan_mode(
                self._device, True, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
            )
            raise_if_error(
                response,
                "fan mode",
                f"{FAN_CIRCULATE_DEFAULT_DUTY_CYCLE} duty cycle",
            )

        else:
            # First reset circulating fan mode state and then force set fan mode
            # The min duty cycle is 10. Otherwise the error "Attempted to set /circulating_fan/min_duty_cycle:0 below allowable value 10" is returned.
            if self._device.capabilities.circulating_fan.capable:
                response = await self.coordinator.client.async_set_circulating_fan_mode(
                    self._device, False, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
                )

                raise_if_error(
                    response, "circulating fan mode", "False with duty cycle of 0"
                )

            response = await self.coordinator.client.async_set_fan_mode(
                self._device, fan_mode
            )
            raise_if_error(response, "fan mode", fan_mode)

        self.async_write_ha_state()
        LOGGER.info("%s: Setting fan_mode to %s", self._device.name, fan_mode)

    async def async_turn_on(self) -> None:
        """Turn thermostat on."""

        # First call base to set the hvac mode and then set fan mode.
        # async_turn_off is not implemented. Base sets OFF hvac mode.
        await super().async_turn_on()

        response = await self.coordinator.client.async_set_fan_mode(
            self._device, FanMode.AUTO.value
        )
        raise_if_error(response, "fan mode", FanMode.AUTO.value)
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""

        response = await self.coordinator.client.async_set_humidification(
            self._device, True, humidity
        )
        raise_if_error(response, "humidity", humidity)
        self.async_write_ha_state()
