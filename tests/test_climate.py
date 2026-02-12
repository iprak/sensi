"""Tests for Sensi climate component."""

from unittest.mock import MagicMock, call, patch

import pytest

from custom_components.sensi import set_config_option
from custom_components.sensi.client import ActionResponse
from custom_components.sensi.climate import SensiThermostat, async_setup_entry
from custom_components.sensi.const import (
    ATTR_CIRCULATING_FAN,
    ATTR_CIRCULATING_FAN_DUTY_CYCLE,
    ATTR_POWER_STATUS,
    CONFIG_FAN_SUPPORT,
    FAN_CIRCULATE_DEFAULT_DUTY_CYCLE,
    SENSI_FAN_AUTO,
    SENSI_FAN_CIRCULATE,
)
from custom_components.sensi.data import FanMode, OperatingMode, SensiDevice
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant


async def test_setup_platform(
    hass: HomeAssistant,
    mock_entry,
    mock_coordinator,
    mock_device,
    mock_device_with_humidification,
) -> None:
    """Test platform setup."""

    mock_coordinator.get_devices = MagicMock(
        return_value=[mock_device, mock_device_with_humidification]
    )

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, async_add_entities)

    assert async_add_entities.called
    assert len(async_add_entities.call_args[0][0]) == 2


async def test_set_hvac_mode(
    hass: HomeAssistant, mock_device, mock_thermostat, mock_coordinator
) -> None:
    """Test async_set_hvac_mode."""

    with (
        patch.object(mock_thermostat, "async_write_ha_state"),
        patch.object(
            mock_thermostat.coordinator.client, "async_set_operating_mode"
        ) as mock_set_operating_mode,
        patch.object(
            mock_coordinator, "async_update_listeners"
        ) as mock_async_update_listeners,
    ):
        mock_set_operating_mode.return_value = ActionResponse(None, "")

        await mock_thermostat.async_set_hvac_mode(HVACMode.HEAT)

        mock_set_operating_mode.assert_called_once_with(mock_device, OperatingMode.HEAT)
        mock_async_update_listeners.assert_called_once()


async def test_set_hvac_mode_invalid(hass: HomeAssistant, mock_thermostat) -> None:
    """Test async_set_hvac_mode with invalid value."""

    with pytest.raises(ValueError):
        await mock_thermostat.async_set_hvac_mode(
            HVACMode.HEAT_COOL
        )  # HEAT_COOL is not supported and evaluated to None OperatingMode


async def test_set_fan_mode_auto(
    hass: HomeAssistant, mock_device, mock_thermostat
) -> None:
    """Test async_set_fan_mode auto."""

    with (
        patch.object(mock_thermostat, "async_write_ha_state"),
        patch.object(
            mock_thermostat.coordinator.client, "async_set_circulating_fan_mode"
        ) as mock_set_circulating_fan_mode,
        patch.object(
            mock_thermostat.coordinator.client, "async_set_fan_mode"
        ) as mock_set_fan_mode,
    ):
        mock_set_circulating_fan_mode.return_value = ActionResponse(None, "")
        mock_set_fan_mode.return_value = ActionResponse(None, "")

        await mock_thermostat.async_set_fan_mode(SENSI_FAN_AUTO)

        mock_set_circulating_fan_mode.assert_called_once_with(
            mock_device, False, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
        )
        mock_set_fan_mode.assert_called_once_with(mock_device, SENSI_FAN_AUTO)


async def test_set_fan_mode_circulate(
    hass: HomeAssistant, mock_device, mock_thermostat
) -> None:
    """Test async_set_fan_mode circulate."""

    with (
        patch.object(mock_thermostat, "async_write_ha_state"),
        patch.object(
            mock_thermostat.coordinator.client, "async_set_circulating_fan_mode"
        ) as mock_set_circulating_fan_mode,
        patch.object(
            mock_thermostat.coordinator.client, "async_set_fan_mode"
        ) as mock_set_fan_mode,
    ):
        mock_set_circulating_fan_mode.return_value = ActionResponse(None, "")
        mock_set_fan_mode.return_value = ActionResponse(None, "")

        await mock_thermostat.async_set_fan_mode(SENSI_FAN_CIRCULATE)

        mock_set_fan_mode.assert_called_once_with(mock_device, SENSI_FAN_AUTO)
        mock_set_circulating_fan_mode.assert_called_once_with(
            mock_device, True, FAN_CIRCULATE_DEFAULT_DUTY_CYCLE
        )


async def test_set_temperature(
    hass: HomeAssistant, mock_device, mock_thermostat, mock_coordinator
) -> None:
    """Test async_set_temperature."""

    temperature = 75
    with (
        patch.object(
            mock_thermostat, "async_write_ha_state"
        ) as mock_async_write_ha_state,
        patch.object(
            mock_coordinator, "async_update_listeners"
        ) as mock_async_update_listeners,
        patch.object(
            mock_thermostat.coordinator.client, "async_set_temperature"
        ) as mock_async_set_temperature,
    ):
        mock_async_set_temperature.return_value = ActionResponse(
            None, {"current_temp": 70, "mode": "heat", "target_temp": 75}
        )

        await mock_thermostat.async_set_temperature(temperature=temperature)

        mock_async_set_temperature.assert_called_once_with(
            mock_device, mock_device.state.operating_mode, temperature
        )
        mock_async_write_ha_state.assert_called_once()
        mock_async_update_listeners.assert_called_once()


async def test_set_temperature_auto(
    hass: HomeAssistant, mock_device, mock_thermostat, mock_coordinator
) -> None:
    """Test async_set_temperature for auto mode."""

    with (
        patch.object(
            mock_thermostat, "async_write_ha_state"
        ) as mock_async_write_ha_state,
        patch.object(
            mock_coordinator, "async_update_listeners"
        ) as mock_async_update_listeners,
        patch.object(
            mock_thermostat.coordinator.client, "async_set_temperature"
        ) as mock_async_set_temperature,
    ):
        mock_async_set_temperature.return_value = ActionResponse(
            None, {"current_temp": 70, "mode": "heat", "target_temp": 75}
        )
        mock_device.state.operating_mode = OperatingMode.AUTO

        await mock_thermostat.async_set_temperature(
            target_temp_low=66, target_temp_high=75
        )

        expected_calls = [
            call(mock_device, OperatingMode.HEAT, 66),
            call(mock_device, OperatingMode.COOL, 75),
        ]

        assert mock_async_set_temperature.call_count == len(expected_calls)
        mock_async_set_temperature.assert_has_calls(expected_calls)

        mock_async_write_ha_state.assert_called_once()
        mock_async_update_listeners.assert_called_once()


async def test_set_fan_mode_invalid(
    hass: HomeAssistant, mock_device, mock_thermostat
) -> None:
    """Test invalid mode for async_set_fan_mode."""

    with pytest.raises(ValueError):
        await mock_thermostat.async_set_fan_mode("INVALID")


class TestSensiThermostatInitialization:
    """Test cases for SensiThermostat initialization."""

    def test_thermostat_is_climate_entity(self, mock_thermostat):
        """Test SensiThermostat is a ClimateEntity."""

        assert isinstance(mock_thermostat, ClimateEntity)

    def test_thermostat_has_entity_name(self, mock_thermostat):
        """Test that mock_thermostat has entity name enabled."""

        assert mock_thermostat.has_entity_name is True


class TestSensiThermostatProperties:
    """Test cases for SensiThermostat properties."""

    def test_name_property(self, mock_thermostat):
        """Test name property returns None for primary entity."""

        assert mock_thermostat.name is None

    def test_current_temperature(self, mock_device, mock_thermostat):
        """Test current_temperature property."""

        assert mock_thermostat.current_temperature == mock_device.state.display_temp

    @pytest.mark.parametrize(
        ("display_scale", "expected"),
        [
            ("c", UnitOfTemperature.CELSIUS),
            ("C", UnitOfTemperature.CELSIUS),
            ("f", UnitOfTemperature.FAHRENHEIT),
            ("F", UnitOfTemperature.FAHRENHEIT),
        ],
    )
    def test_temperature_unit(
        self, hass: HomeAssistant, mock_json, mock_entry, display_scale, expected
    ):
        """Test temperature_unit property for Celsius."""

        mock_json["state"]["display_scale"] = display_scale
        _, device = SensiDevice.create(mock_json)
        thermostat = SensiThermostat(hass, device, mock_entry)

        assert thermostat.temperature_unit == expected

    def test_current_humidity(self, mock_device, mock_thermostat):
        """Test current_humidity property."""

        assert mock_thermostat.current_humidity == mock_device.state.humidity


class TestSensiThermostatHvacModes:
    """Test cases for HVAC modes."""

    def test_hvac_mode_off(self, mock_device, mock_thermostat):
        """Test hvac_mode when operating mode is OFF."""

        mock_device.state.operating_mode = OperatingMode.OFF

        assert mock_thermostat.hvac_mode == HVACMode.OFF

    def test_hvac_mode_heat(self, mock_device, mock_thermostat):
        """Test hvac_mode when operating mode is HEAT."""

        mock_device.state.operating_mode = OperatingMode.HEAT

        assert mock_thermostat.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_cool(self, mock_device, mock_thermostat):
        """Test hvac_mode when operating mode is COOL."""

        mock_device.state.operating_mode = OperatingMode.COOL

        assert mock_thermostat.hvac_mode == HVACMode.COOL

    def test_hvac_mode_auto(self, mock_device, mock_thermostat):
        """Test hvac_mode when operating mode is AUTO."""

        mock_device.state.operating_mode = OperatingMode.AUTO

        assert mock_thermostat.hvac_mode == HVACMode.AUTO

    def test_hvac_modes_available(self, mock_device, mock_thermostat):
        """Test available hvac modes based on capabilities."""

        modes = mock_thermostat.hvac_modes
        assert isinstance(modes, list)
        assert len(modes) > 0

    def test_hvac_modes_contains_off(self, mock_device, mock_thermostat):
        """Test that hvac_modes contains OFF when capable."""

        mock_device.capabilities.operating_mode_settings.off = True

        assert HVACMode.OFF in mock_thermostat.hvac_modes


@pytest.mark.parametrize(
    ("mode", "heat", "cool", "expected"),
    [
        (OperatingMode.OFF, 0, 0, HVACAction.OFF),
        (OperatingMode.HEAT, 100, 0, HVACAction.HEATING),
        (OperatingMode.COOL, 0, 100, HVACAction.COOLING),
        (OperatingMode.HEAT, 0, 0, HVACAction.IDLE),
        (OperatingMode.AUX, 0, 0, HVACAction.HEATING),
    ],
)
def test_hvac_action(mock_device, mock_thermostat, mode, heat, cool, expected) -> None:
    """Test cases for HVAC action determination."""
    mock_device.state.operating_mode = mode
    mock_device.state.demand_status.heat = heat
    mock_device.state.demand_status.cool = cool
    assert mock_thermostat.hvac_action == expected


class TestSensiThermostatFanModes:
    """Test cases for fan mode support."""

    def test_fan_mode_property_auto(self, mock_device, mock_thermostat):
        """Test fan_mode property when set to AUTO."""

        mock_device.state.fan_mode = FanMode.AUTO
        mock_device.state.circulating_fan.enabled = False

        assert mock_thermostat.fan_mode == FanMode.AUTO.value

    def test_fan_mode_property_on(self, mock_device, mock_thermostat):
        """Test fan_mode property when set to ON."""

        mock_device.state.fan_mode = FanMode.ON

        assert mock_thermostat.fan_mode == FanMode.ON.value

    def test_fan_mode_circulate_when_enabled(self, mock_device, mock_thermostat):
        """Test fan_mode returns circulate when enabled."""

        mock_device.state.fan_mode = FanMode.AUTO
        mock_device.state.circulating_fan.enabled = True

        assert mock_thermostat.fan_mode == SENSI_FAN_CIRCULATE

    def test_max_temp_in_heat_mode(self, mock_device, mock_thermostat):
        """Test max_temp when in heat mode."""

        mock_device.state.operating_mode = OperatingMode.HEAT

        assert mock_thermostat.max_temp is not None


class TestSensiThermostatTargetTemperature:
    """Test cases for target temperature."""

    def test_target_temperature_off_mode(self, mock_device, mock_thermostat):
        """Test target_temperature returns None when OFF."""

        mock_device.state.operating_mode = OperatingMode.OFF

        assert mock_thermostat.target_temperature is None

    def test_target_temperature_heating(self, mock_device, mock_thermostat):
        """Test target_temperature when heating."""

        mock_device.state.operating_mode = OperatingMode.HEAT
        mock_device.state.demand_status.heat = 100

        assert mock_thermostat.target_temperature == mock_device.state.current_heat_temp

    def test_target_temperature_cooling(self, mock_device, mock_thermostat):
        """Test target_temperature when cooling."""

        mock_device.state.operating_mode = OperatingMode.COOL
        mock_device.state.demand_status.cool = 100

        assert mock_thermostat.target_temperature == mock_device.state.current_cool_temp


class TestSensiThermostatExtraStateAttributes:
    """Test cases for extra state attributes."""

    def test_extra_state_attributes_contains_fan_info(
        self, mock_device, mock_thermostat
    ):
        """Test extra_state_attributes contains fan information."""

        attrs = mock_thermostat.extra_state_attributes
        assert attrs is not None
        assert ATTR_CIRCULATING_FAN in attrs
        assert ATTR_CIRCULATING_FAN_DUTY_CYCLE in attrs
        assert ATTR_POWER_STATUS in attrs

    def test_extra_state_attributes_fan_enabled(self, mock_device, mock_thermostat):
        """Test extra_state_attributes shows fan enabled state."""

        mock_device.state.circulating_fan.enabled = True

        attrs = mock_thermostat.extra_state_attributes
        assert attrs[ATTR_CIRCULATING_FAN] is True

    def test_extra_state_attributes_fan_duty_cycle(self, mock_device, mock_thermostat):
        """Test extra_state_attributes shows fan duty cycle."""

        mock_device.state.circulating_fan.duty_cycle = 50

        attrs = mock_thermostat.extra_state_attributes
        assert attrs[ATTR_CIRCULATING_FAN_DUTY_CYCLE] == 50


def test_supported_features(mock_device, mock_thermostat) -> None:
    """Test supported features."""

    mock_device.state.operating_mode = OperatingMode.HEAT
    features = mock_thermostat.supported_features

    assert ClimateEntityFeature.TURN_ON in features
    assert ClimateEntityFeature.TURN_OFF in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE_RANGE not in features
    assert ClimateEntityFeature.TARGET_HUMIDITY not in features
    assert ClimateEntityFeature.FAN_MODE in features


def test_supported_features_auto(mock_device, mock_thermostat) -> None:
    """Test supported features in auto mode."""

    mock_device.state.operating_mode = OperatingMode.HEAT
    features = mock_thermostat.supported_features

    assert ClimateEntityFeature.TURN_ON in features
    assert ClimateEntityFeature.TURN_OFF in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE_RANGE not in features
    assert ClimateEntityFeature.TARGET_HUMIDITY not in features
    assert ClimateEntityFeature.FAN_MODE in features


def test_supported_features_fan_disabled(
    hass: HomeAssistant, mock_entry, mock_device, mock_thermostat
) -> None:
    """Test supported features when fan is disabled."""

    mock_device.state.operating_mode = OperatingMode.HEAT

    set_config_option(hass, mock_device, mock_entry, CONFIG_FAN_SUPPORT, False)

    features = mock_thermostat.supported_features

    assert ClimateEntityFeature.TURN_ON in features
    assert ClimateEntityFeature.TURN_OFF in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE_RANGE not in features
    assert ClimateEntityFeature.TARGET_HUMIDITY not in features
    assert ClimateEntityFeature.FAN_MODE not in features


def test_supported_features_humidification(
    mock_device_with_humidification, mock_thermostat_with_humidification
) -> None:
    """Test supported features."""

    mock_device_with_humidification.state.operating_mode = OperatingMode.HEAT
    mock_device_with_humidification.state.humidity_control.humidification.enabled = True

    features = mock_thermostat_with_humidification.supported_features

    assert ClimateEntityFeature.TURN_ON in features
    assert ClimateEntityFeature.TURN_OFF in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE_RANGE not in features
    assert ClimateEntityFeature.TARGET_HUMIDITY in features
    assert ClimateEntityFeature.FAN_MODE in features


class TestSensiThermostatHumidity:
    """Test cases for humidity control."""

    def test_target_humidity(
        self, mock_thermostat, mock_thermostat_with_humidification
    ):
        """Test target_humidity property."""

        # target_humidity returns None if humidification is disabled
        assert mock_thermostat.target_humidity is None  # Humidification not supported
        assert isinstance(mock_thermostat_with_humidification.target_humidity, int)

    def test_min_humidity(self, mock_thermostat, mock_thermostat_with_humidification):
        """Test min_humidity property."""

        assert mock_thermostat.min_humidity is None  # Humidification not supported

        min_humid = mock_thermostat_with_humidification.min_humidity
        assert isinstance(min_humid, int)
        assert 0 <= min_humid <= 100

    def test_max_humidity(self, mock_thermostat, mock_thermostat_with_humidification):
        """Test max_humidity property."""

        assert mock_thermostat.max_humidity is None  # Humidification not supported

        max_humid = mock_thermostat_with_humidification.max_humidity
        assert isinstance(max_humid, int)
        assert 0 <= max_humid <= 100
