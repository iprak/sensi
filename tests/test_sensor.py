"""Tests for Sensi sensor component."""

from unittest.mock import MagicMock

import pytest

from custom_components.sensi.const import ATTR_BATTERY_VOLTAGE
from custom_components.sensi.coordinator import SensiDevice
from custom_components.sensi.sensor import (
    SENSOR_TYPES,
    SensiSensorEntityDescription,
    async_setup_entry,
    calculate_battery_level,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
    assert len(async_add_entities.call_args[0][0]) == 7 * 2  # 7 = from SENSOR_TYPES


async def test_sensor_native_value(
    hass: HomeAssistant,
    mock_entry,
    mock_coordinator,
    mock_device,
) -> None:
    """Test platform setup."""

    mock_coordinator.get_devices = MagicMock(return_value=[mock_device])

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]

    # First is Temperature
    assert entities[0].native_value == mock_device.state.display_temp
    assert entities[0].native_unit_of_measurement == mock_device.state.temperature_unit
    assert entities[0].extra_state_attributes is None
    assert entities[0].icon is None

    # 3rd is Battery
    battery_voltage = mock_device.state.battery_voltage
    assert entities[2].native_value == calculate_battery_level(battery_voltage)
    assert entities[2].native_unit_of_measurement == PERCENTAGE
    assert entities[2].extra_state_attributes == {ATTR_BATTERY_VOLTAGE: battery_voltage}

    # 4 is Min setpoint
    assert entities[3].icon == "mdi:thermometer-low"


class TestCalculateBatteryLevel:
    """Test cases for calculate_battery_level function."""

    def test_battery_level_above_3000_mv(self):
        """Test battery level when voltage is 3.0V or higher."""
        assert calculate_battery_level(3.0) == 100
        assert calculate_battery_level(3.1) == 100
        assert calculate_battery_level(3.5) == 100

    def test_battery_level_2900_to_3000_mv(self):
        """Test battery level in 2.9V to 3.0V range."""
        result = calculate_battery_level(2.95)
        assert 50 <= result <= 100

    def test_battery_level_2740_to_2900_mv(self):
        """Test battery level in 2.74V to 2.9V range."""
        result = calculate_battery_level(2.82)
        assert 18 <= result <= 42

    def test_battery_level_2440_to_2740_mv(self):
        """Test battery level in 2.44V to 2.74V range."""
        result = calculate_battery_level(2.59)
        assert 6 <= result <= 18

    def test_battery_level_2100_to_2440_mv(self):
        """Test battery level in 2.1V to 2.44V range."""
        result = calculate_battery_level(2.27)
        assert 0 <= result <= 6

    def test_battery_level_below_2100_mv(self):
        """Test battery level when voltage is below 2.1V."""
        assert calculate_battery_level(2.0) == 0
        assert calculate_battery_level(1.5) == 0
        assert calculate_battery_level(0.5) == 0

    def test_battery_level_with_none(self):
        """Test battery level with None voltage."""
        assert calculate_battery_level(None) is None

    def test_battery_level_edge_cases(self):
        """Test battery level at exact boundaries."""
        assert calculate_battery_level(3.0) == 100
        assert calculate_battery_level(2.1) >= 0
        assert calculate_battery_level(2.1) <= 6

    def test_battery_level_typical_aa_battery(self):
        """Test with typical AA battery voltages."""
        # Fresh AA battery ~1.5V, fresh two-pack ~3.0V
        assert calculate_battery_level(3.0) == 100
        # Partially depleted
        result = calculate_battery_level(2.5)
        assert 0 <= result <= 42
        # Nearly dead
        assert calculate_battery_level(2.1) >= 0

    def test_battery_level_incremental_decrease(self):
        """Test that battery level decreases as voltage decreases."""
        level_high = calculate_battery_level(2.9)
        level_mid = calculate_battery_level(2.5)
        level_low = calculate_battery_level(2.1)
        assert level_high >= level_mid >= level_low


class TestSensiSensorEntityDescription:
    """Test cases for SensiSensorEntityDescription class."""

    def test_sensor_description_creation(self):
        """Test creating a SensiSensorEntityDescription."""
        desc = SensiSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            value_fn=lambda device: 42,
        )
        assert desc.key == "test_sensor"
        assert desc.name == "Test Sensor"
        assert desc.value_fn is not None
        assert desc.extra_state_attributes_fn is None

    def test_sensor_description_with_attributes_fn(self):
        """Test description with extra_state_attributes_fn."""

        def attrs_fn():
            return {"extra": "value"}

        desc = SensiSensorEntityDescription(
            key="test",
            name="Test",
            value_fn=lambda device: 100,
            extra_state_attributes_fn=attrs_fn,
        )
        assert desc.extra_state_attributes_fn is not None

    def test_sensor_description_frozen(self):
        """Test that SensiSensorEntityDescription is frozen."""
        desc = SensiSensorEntityDescription(
            key="test",
            name="Test",
            value_fn=lambda device: 1,
        )
        with pytest.raises(AttributeError):
            desc.key = "new_key"

    def test_sensor_description_with_device_class(self):
        """Test description with device class."""
        desc = SensiSensorEntityDescription(
            key="temp",
            name="Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            value_fn=lambda device: 72,
        )
        assert desc.device_class == SensorDeviceClass.TEMPERATURE

    def test_sensor_description_with_unit(self):
        """Test description with native unit of measurement."""
        desc = SensiSensorEntityDescription(
            key="humidity",
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda device: 50,
        )
        assert desc.native_unit_of_measurement == PERCENTAGE


class TestSensorTypes:
    """Test cases for SENSOR_TYPES configuration."""

    def test_sensor_types_not_empty(self):
        """Test that SENSOR_TYPES is not empty."""
        assert len(SENSOR_TYPES) > 0

    def test_all_sensors_have_key(self):
        """Test that all sensor types have a key."""
        for sensor in SENSOR_TYPES:
            assert sensor.key is not None
            assert len(sensor.key) > 0

    def test_all_sensors_have_name(self):
        """Test that all sensor types have a name."""
        for sensor in SENSOR_TYPES:
            assert sensor.name is not None
            assert len(sensor.name) > 0

    def test_all_sensors_have_value_fn(self):
        """Test that all sensor types have a value function."""
        for sensor in SENSOR_TYPES:
            assert sensor.value_fn is not None

    def test_all_sensor_keys_unique(self):
        """Test that all sensor keys are unique."""
        keys = [sensor.key for sensor in SENSOR_TYPES]
        assert len(keys) == len(set(keys))

    def test_temperature_sensor_in_types(self):
        """Test that temperature sensor is defined."""
        temp_sensors = [s for s in SENSOR_TYPES if s.key == "temperature"]
        assert len(temp_sensors) == 1
        assert temp_sensors[0].device_class == SensorDeviceClass.TEMPERATURE

    def test_humidity_sensor_in_types(self):
        """Test that humidity sensor is defined."""
        humidity_sensors = [s for s in SENSOR_TYPES if s.key == "humidity"]
        assert len(humidity_sensors) == 1
        assert humidity_sensors[0].device_class == SensorDeviceClass.HUMIDITY

    def test_battery_sensor_in_types(self):
        """Test that battery sensor is defined."""
        battery_sensors = [s for s in SENSOR_TYPES if s.key == "battery"]
        assert len(battery_sensors) == 1
        assert battery_sensors[0].device_class == SensorDeviceClass.BATTERY
        assert battery_sensors[0].extra_state_attributes_fn is not None

    def test_fan_speed_sensor_in_types(self):
        """Test that fan speed sensor is defined."""
        fan_sensors = [s for s in SENSOR_TYPES if s.key == "fan_speed"]
        assert len(fan_sensors) == 1

    def test_wifi_strength_sensor_in_types(self):
        """Test that wifi strength sensor is defined."""
        wifi_sensors = [s for s in SENSOR_TYPES if s.key == "wifi_strength"]
        assert len(wifi_sensors) == 1

    def test_temperature_sensor_configuration(self):
        """Test temperature sensor configuration."""
        temp_sensor = next(s for s in SENSOR_TYPES if s.key == "temperature")
        assert temp_sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert temp_sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT

    def test_humidity_sensor_configuration(self):
        """Test humidity sensor configuration."""
        humidity_sensor = next(s for s in SENSOR_TYPES if s.key == "humidity")
        assert humidity_sensor.device_class == SensorDeviceClass.HUMIDITY
        assert humidity_sensor.native_unit_of_measurement == PERCENTAGE

    def test_battery_sensor_has_attributes_fn(self):
        """Test battery sensor has attributes function."""
        battery_sensor = next(s for s in SENSOR_TYPES if s.key == "battery")
        assert battery_sensor.extra_state_attributes_fn is not None
        # Test the function returns a dict
        mock_device = type(
            "MockDevice", (), {"state": type("State", (), {"battery_voltage": 3.0})()}
        )()
        attrs = battery_sensor.extra_state_attributes_fn(mock_device)
        assert isinstance(attrs, dict)

    def test_diagnostic_sensors_disabled_by_default(self):
        """Test that diagnostic sensors are disabled by default."""
        diagnostic_keys = [
            "cool_min_temp",
            "heat_max_temp",
            "fan_speed",
            "wifi_strength",
            "battery",
        ]
        for sensor in SENSOR_TYPES:
            if sensor.key in diagnostic_keys:
                assert sensor.entity_registry_enabled_default in [False, None]

    def test_sensor_value_functions_callable(self):
        """Test that all value functions are callable."""
        for sensor in SENSOR_TYPES:
            assert callable(sensor.value_fn)

    def test_battery_sensor_value_function(self, mock_json):
        """Test battery sensor value function."""

        _have_state, device = SensiDevice.create(mock_json)
        battery_sensor = next(s for s in SENSOR_TYPES if s.key == "battery")
        value = battery_sensor.value_fn(device)
        assert value is None or isinstance(value, int)

    def test_temperature_sensor_value_function(self, mock_json):
        """Test temperature sensor value function."""

        _have_state, device = SensiDevice.create(mock_json)
        temp_sensor = next(s for s in SENSOR_TYPES if s.key == "temperature")
        value = temp_sensor.value_fn(device)
        assert isinstance(value, (int, float))

    def test_humidity_sensor_value_function(self, mock_json):
        """Test humidity sensor value function."""

        _have_state, device = SensiDevice.create(mock_json)
        humidity_sensor = next(s for s in SENSOR_TYPES if s.key == "humidity")
        value = humidity_sensor.value_fn(device)
        assert isinstance(value, int)

    def test_fan_speed_sensor_value_function(self, mock_json):
        """Test fan speed sensor value function."""

        __have_state, device = SensiDevice.create(mock_json)
        fan_sensor = next(s for s in SENSOR_TYPES if s.key == "fan_speed")
        value = fan_sensor.value_fn(device)
        assert isinstance(value, int)

    def test_wifi_strength_sensor_value_function(self, mock_json):
        """Test wifi strength sensor value function."""

        __have_state, device = SensiDevice.create(mock_json)
        wifi_sensor = next(s for s in SENSOR_TYPES if s.key == "wifi_strength")
        value = wifi_sensor.value_fn(device)
        assert isinstance(value, int)

    def test_cool_min_temp_sensor_configuration(self):
        """Test cool min temp sensor configuration."""
        cool_min = next(s for s in SENSOR_TYPES if s.key == "cool_min_temp")
        assert cool_min.device_class == SensorDeviceClass.TEMPERATURE
        assert cool_min.entity_registry_enabled_default is False

    def test_heat_max_temp_sensor_configuration(self):
        """Test heat max temp sensor configuration."""
        heat_max = next(s for s in SENSOR_TYPES if s.key == "heat_max_temp")
        assert heat_max.device_class == SensorDeviceClass.TEMPERATURE
        assert heat_max.entity_registry_enabled_default is False

    def test_sensors_with_icons(self):
        """Test sensors that have icons defined."""
        icons_expected = {
            "fan_speed": "mdi:fan",
            "wifi_strength": "mdi:wifi-strength-outline",
            "cool_min_temp": "mdi:thermometer-low",
            "heat_max_temp": "mdi:thermometer-high",
        }
        for key, icon in icons_expected.items():
            sensor = next(s for s in SENSOR_TYPES if s.key == key)
            assert sensor.icon == icon
