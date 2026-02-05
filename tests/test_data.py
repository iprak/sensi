"""Tests for Sensi data component."""

import pytest

from custom_components.sensi.coordinator import SensiDevice
from custom_components.sensi.data import (
    CirculatingFan,
    DemandStatus,
    FanMode,
    Firmware,
    HumidityControl,
    OperatingMode,
    State,
    ThermostatInfo,
    get_hvac_mode_from_operating_mode,
    get_operating_mode_from_hvac_mode,
)
from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature


class TestOperatingMode:
    """Test cases for OperatingMode enum."""

    def test_operating_mode_values(self):
        """Test OperatingMode enum values."""
        assert OperatingMode.OFF == "off"
        assert OperatingMode.AUX == "aux"
        assert OperatingMode.HEAT == "heat"
        assert OperatingMode.COOL == "cool"
        assert OperatingMode.AUTO == "auto"
        assert OperatingMode.UNKNOWN == "unknown"


@pytest.mark.parametrize(
    ("operating_mode", "expected_hvac"),
    [
        (OperatingMode.HEAT, HVACMode.HEAT),
        (OperatingMode.AUX, HVACMode.HEAT),
        (OperatingMode.COOL, HVACMode.COOL),
        (OperatingMode.AUTO, HVACMode.AUTO),
        (OperatingMode.OFF, HVACMode.OFF),
        (OperatingMode.UNKNOWN, None),
    ],
)
def test_hvac_mode_from_operating_mode(operating_mode, expected_hvac) -> None:
    """Test converting OperatingMode.HEAT to HVACMode."""
    assert get_hvac_mode_from_operating_mode(operating_mode) == expected_hvac


@pytest.mark.parametrize(
    ("hvac", "expected_operating_mode"),
    [
        (HVACMode.HEAT, OperatingMode.HEAT),
        (HVACMode.COOL, OperatingMode.COOL),
        (HVACMode.AUTO, OperatingMode.AUTO),
        (
            HVACMode.OFF,
            OperatingMode.OFF,
        ),
        (HVACMode.DRY, None),
    ],
)
def test_hvac_mode_heat_to_operating(hvac, expected_operating_mode) -> None:
    """Test converting HVACMode.HEAT to OperatingMode."""
    assert get_operating_mode_from_hvac_mode(hvac) == expected_operating_mode


class TestCirculatingFan:
    """Test cases for CirculatingFan class."""

    def test_circulating_fan_enabled(self):
        """Test CirculatingFan with enabled state."""
        data = {"enabled": "on", "duty_cycle": 50}
        fan = CirculatingFan(data)
        assert fan.enabled is True
        assert fan.duty_cycle == 50

    def test_circulating_fan_disabled(self):
        """Test CirculatingFan with disabled state."""
        data = {"enabled": "off", "duty_cycle": 0}
        fan = CirculatingFan(data)
        assert fan.enabled is False
        assert fan.duty_cycle == 0

    def test_circulating_fan_empty_data(self):
        """Test CirculatingFan with empty data."""
        data = {}
        fan = CirculatingFan(data)
        assert fan.enabled is False
        assert fan.duty_cycle == 0

    def test_circulating_fan_with_boolean_values(self):
        """Test CirculatingFan with boolean values."""
        data = {"enabled": True, "duty_cycle": 75}
        fan = CirculatingFan(data)
        assert fan.enabled is True
        assert fan.duty_cycle == 75


class TestDemandStatus:
    """Test cases for DemandStatus class."""

    def test_demand_status_with_all_fields(self):
        """Test DemandStatus with all fields."""
        data = {
            "heat": 1,
            "fan": 1,
            "cool": 0,
            "aux": 0,
            "last": "heat",
            "last_start": 1234567890,
        }
        status = DemandStatus(data)
        assert status.heat == 1
        assert status.fan == 1
        assert status.cool == 0
        assert status.aux == 0
        assert status.last == "heat"
        assert status.last_start == 1234567890

    def test_demand_status_with_empty_data(self):
        """Test DemandStatus with empty data."""
        data = {}
        status = DemandStatus(data)
        assert status.heat == 0
        assert status.fan == 0
        assert status.cool == 0
        assert status.aux == 0
        assert status.last == ""
        assert status.last_start is None

    def test_demand_status_cooling(self):
        """Test DemandStatus with cooling active."""
        data = {
            "heat": 0,
            "fan": 1,
            "cool": 1,
            "aux": 0,
            "last": "cool",
        }
        status = DemandStatus(data)
        assert status.cool == 1
        assert status.last == "cool"

    def test_demand_status_parsing(self, mock_json) -> None:
        """Test DemandStatus parsing using sample.json."""
        state_dict = mock_json.get("state", {})
        state_obj = State(state_dict)

        assert isinstance(state_obj.demand_status, DemandStatus)
        assert state_obj.demand_status.fan == 0
        assert state_obj.demand_status.last == "heat"


class TestFirmware:
    """Test cases for Firmware class."""

    def test_firmware_with_all_fields(self):
        """Test Firmware with all fields."""
        data = {
            "firmware_version": "6004850907",
            "bootloader_version": "6003970905",
            "wifi_version": "6004820907",
        }
        firmware = Firmware(data)
        assert firmware.firmware_version == "6004850907"
        assert firmware.bootloader_version == "6003970905"
        assert firmware.wifi_version == "6004820907"

    def test_firmware_with_empty_data(self):
        """Test Firmware with empty data."""
        data = {}
        firmware = Firmware(data)
        assert firmware.firmware_version == ""
        assert firmware.bootloader_version == ""
        assert firmware.wifi_version == ""


class TestThermostatInfo:
    """Test cases for ThermostatInfo class."""

    def test_thermostat_info_with_all_fields(self, mock_json):
        """Test ThermostatInfo with valid data."""
        info_data = {
            "test_date": "11/14/2018",
            "build_date": "11/14/2018",
            "serial_number": "42WFRP46B00220",
            "unique_hardware_id": 1,
            "model_number": "1F87U-42WFC",
            "images": {
                "bootloader_version": "6003970905",
                "firmware_version": "6004850907",
                "wifi_version": "6004820907",
            },
            "wifi_mac_address": "346F920C0B07",
            "last_changed_timestamp": 1759918908,
        }
        info = ThermostatInfo(info_data)
        assert info.test_date == "11/14/2018"
        assert info.build_date == "11/14/2018"
        assert info.serial_number == "42WFRP46B00220"
        assert info.unique_hardware_id == 1
        assert info.model_number == "1F87U-42WFC"
        assert info.wifi_mac_address == "346F920C0B07"
        assert info.last_changed_timestamp == 1759918908
        assert isinstance(info.images, Firmware)

    def test_thermostat_info_with_empty_data(self):
        """Test ThermostatInfo with empty data."""
        data = {}
        info = ThermostatInfo(data)
        assert info.test_date == ""
        assert info.build_date == ""
        assert info.serial_number == ""
        assert info.model_number == ""

    def test_thermostat_info_string_representation(self):
        """Test ThermostatInfo string representation."""
        data = {
            "model_number": "1F87U-42WFC",
            "serial_number": "42WFRP46B00220",
            "unique_hardware_id": 1,
            "wifi_mac_address": "346F920C0B07",
        }
        info = ThermostatInfo(data)
        info_str = str(info)
        assert "ThermostatInfo" in info_str
        assert "model=" in info_str
        assert "1F87U-42WFC" in info_str


class TestState:
    """Test cases for State class."""

    def test_state_with_fahrenheit(self, mock_json):
        """Test State with Fahrenheit temperature scale."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert state.display_scale == "f"
        assert state.temperature_unit == UnitOfTemperature.FAHRENHEIT

    def test_state_with_celsius(self):
        """Test State with Celsius temperature scale."""
        data = {
            "display_scale": "c",
            "display_temp": 20.0,
            "humidity": 50,
        }
        state = State(data)
        assert state.display_scale == "c"
        assert state.temperature_unit == UnitOfTemperature.CELSIUS

    def test_state_temperature_values(self, mock_json):
        """Test State temperature values."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert state.display_temp is not None
        assert state.current_heat_temp is not None
        assert state.current_cool_temp is not None

    def test_state_with_empty_data(self):
        """Test State with empty data."""
        data = {}
        state = State(data)
        assert state.status == ""
        assert state.humidity is None
        assert state.display_temp is None
        assert state.battery_voltage is None

    def test_state_humidity_values(self, mock_json):
        """Test State humidity values."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert state.humidity >= 0
        assert state.humidity <= 100

    def test_state_operating_mode(self, mock_json):
        """Test State operating mode."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert isinstance(state.operating_mode, OperatingMode)

    def test_state_fan_mode(self, mock_json):
        """Test State fan mode."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert isinstance(state.fan_mode, FanMode)

    def test_state_with_circulating_fan(self, mock_json):
        """Test State with circulating fan data."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert isinstance(state.circulating_fan, CirculatingFan)

    def test_state_with_humidity_control(self, mock_json):
        """Test State with humidity control data."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert isinstance(state.humidity_control, HumidityControl)

    def test_state_string_representation(self, mock_json):
        """Test State string representation."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        state_str = str(state)
        assert "State(" in state_str
        assert "operating_mode=" in state_str
        assert "display_temp=" in state_str

    def test_state_with_custom_offsets(self):
        """Test State with temperature and humidity offsets."""
        data = {
            "temp_offset": 2,
            "humidity_offset": -5,
        }
        state = State(data)
        assert state.temp_offset == 2
        assert state.humidity_offset == -5

    def test_state_with_setpoint_values(self):
        """Test State with setpoint temperature values."""
        data = {
            "current_heat_temp": 68,
            "current_cool_temp": 76,
            "heat_max_temp": 77,
            "cool_min_temp": 75,
        }
        state = State(data)
        assert state.current_heat_temp == 68
        assert state.current_cool_temp == 76
        assert state.heat_max_temp == 77
        assert state.cool_min_temp == 75

    def test_state_power_status(self, mock_json):
        """Test State power status."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert state.power_status in ["c_wire", "battery", ""]

    def test_state_wifi_connection_quality(self, mock_json):
        """Test State wifi connection quality."""
        state_dict = mock_json.get("state", {})
        state = State(state_dict)
        assert isinstance(state.wifi_connection_quality, int)


def test_sensi_device_create_with_state(mock_json) -> None:
    """Test SensiDevice.create with valid state data."""
    have_state, device = SensiDevice.create(mock_json)

    assert have_state is True
    assert device.identifier == mock_json.get("icd_id")
    assert device.name == mock_json.get("registration", {}).get("name")
    assert isinstance(device.state, State)


def test_sensi_device_create_without_state(mock_json) -> None:
    """Test SensiDevice.create without state data."""
    data = {
        "icd_id": "test-id",
        "registration": {"name": "Test Device"},
        "capabilities": {},
        "thermostat_info": {},
    }

    have_state, device = SensiDevice.create(data)

    assert have_state is False
    assert device.identifier == "test-id"


def test_sensi_device_create_missing_fields(mock_json) -> None:
    """Test SensiDevice.create with missing optional fields."""
    data = {"icd_id": "test-id"}

    have_state, device = SensiDevice.create(data)

    assert have_state is False
    assert device.identifier == "test-id"
    assert device.name == ""


class TestSensiDevice:
    """Test cases for SensiDevice class."""

    def test_sensi_device_update_state(self, mock_json):
        """Test SensiDevice.update_state method."""
        have_state, device = SensiDevice.create(mock_json)
        assert have_state is True

        new_state_data = {
            "state": {
                "display_temp": 72.5,
                "humidity": 45,
                "operating_mode": "cool",
            }
        }

        result = device.update_state(new_state_data)
        assert result is True
        assert device.state.display_temp == 72.5
        assert device.state.humidity == 45

    def test_sensi_device_update_state_no_state_data(self, mock_json):
        """Test SensiDevice.update_state with no state data."""
        _have_state, device = SensiDevice.create(mock_json)

        result = device.update_state({})
        assert result is False

    def test_sensi_device_info_attribute(self, mock_json):
        """Test SensiDevice has info attribute."""
        _have_state, device = SensiDevice.create(mock_json)
        assert device.info is not None
        assert isinstance(device.info, ThermostatInfo)

    def test_sensi_device_capabilities_attribute(self, mock_json):
        """Test SensiDevice has capabilities attribute."""
        _have_state, device = SensiDevice.create(mock_json)
        assert device.capabilities is not None

    def test_sensi_device_update_capabilities(self, mock_json):
        """Test SensiDevice capabilities update."""
        _have_state, device = SensiDevice.create(mock_json)
        current_capabilities = device.capabilities
        device.update_capabilities({"last_changed_timestamp": 1756195713})

        assert device.capabilities is not None
        assert device.capabilities != current_capabilities

    def test_sensi_device_update_info(self, mock_json):
        """Test SensiDevice info update."""
        _have_state, device = SensiDevice.create(mock_json)
        current_info = device.info
        device.update_info({"test_date": "11/14/2018"})

        assert device.info is not None
        assert device.info != current_info
