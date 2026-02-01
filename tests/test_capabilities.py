"""Tests for Sensi capabilities module."""

from custom_components.sensi.capabilities import (
    MAX_COOL_SETPOINT,
    MAX_HEAT_SETPOINT,
    MIN_COOL_SETPOINT,
    MIN_HEAT_SETPOINT,
    Capabilities,
    CirculatingFanCapabilities,
    FanModes,
    HumidityCapabilities,
    HumidityControlCapabilities,
    SystemModes,
)


class TestSystemModes:
    """Test cases for SystemModes class."""

    def test_system_modes(self):
        """Test SystemModes with some modes disabled."""
        data = {
            "off": "yes",
            "heat": "yes",
            "cool": "no",
            "aux": "no",
            "auto": "yes",
        }
        modes = SystemModes(data)
        assert modes.off is True
        assert modes.heat is True
        assert modes.cool is False
        assert modes.aux is False
        assert modes.auto is True

    def test_system_modes_with_empty_data(self):
        """Test SystemModes with empty data dict."""
        data = {}
        modes = SystemModes(data)
        assert modes.off is False
        assert modes.heat is False
        assert modes.cool is False
        assert modes.aux is False
        assert modes.auto is False


class TestCirculatingFanCapabilities:
    """Test cases for CirculatingFanCapabilities class."""

    def test_circulating_fan_capabilities(self):
        """Test CirculatingFanCapabilities with valid data."""
        data = {
            "capable": "yes",
            "max_duty_cycle": 100,
            "min_duty_cycle": 10,
            "step": 5,
        }
        fan = CirculatingFanCapabilities(data)
        assert fan.capable is True
        assert fan.max_duty_cycle == 100
        assert fan.min_duty_cycle == 10
        assert fan.step == 5

    def test_circulating_fan_capabilities_with_empty_data(self):
        """Test CirculatingFanCapabilities with empty data."""
        data = {}
        fan = CirculatingFanCapabilities(data)
        assert fan.capable is False
        assert fan.max_duty_cycle == 0
        assert fan.min_duty_cycle == 0
        assert fan.step == 0


class TestFanModes:
    """Test cases for FanModes class."""

    def test_fan_modes(self):
        """Test FanModes with some modes disabled."""
        data = {"auto": "yes", "on": "yes", "smart": "no"}
        modes = FanModes(data)
        assert modes.auto is True
        assert modes.on is True
        assert modes.smart is False

    def test_fan_modes_with_empty_data(self):
        """Test FanModes with empty data."""
        data = {}
        modes = FanModes(data)
        assert modes.auto is False
        assert modes.on is False
        assert modes.smart is False


class TestHumidityCapabilities:
    """Test cases for HumidityCapabilities class."""

    def test_humidity_capabilities(self):
        """Test HumidityCapabilities for humidification."""
        data = {"step": 5, "min": 5, "max": 50, "types": ["humidifier"]}
        humidity = HumidityCapabilities(data)
        assert humidity.step == 5
        assert humidity.min == 5
        assert humidity.max == 50
        assert humidity.types == ["humidifier"]

    def test_humidity_capabilities_with_empty_data(self):
        """Test HumidityCapabilities with empty data."""
        data = {}
        humidity = HumidityCapabilities(data)
        assert humidity.types == []


class TestHumidityControlCapabilities:
    """Test cases for HumidityControlCapabilities class."""

    def test_humidity_control_capabilities_with_data(self):
        """Test HumidityControlCapabilities with valid data."""
        data = {
            "humidification": {
                "step": 5,
                "min": 5,
                "max": 50,
                "types": ["humidifier"],
            },
            "dehumidification": {
                "step": 5,
                "min": 40,
                "max": 95,
                "types": ["overcooling"],
            },
        }
        humidity_control = HumidityControlCapabilities(data)
        assert humidity_control.humidification.min == 5
        assert humidity_control.humidification.max == 50
        assert humidity_control.dehumidification.min == 40
        assert humidity_control.dehumidification.max == 95

    def test_humidity_control_capabilities_with_empty_data(self):
        """Test HumidityControlCapabilities with empty data."""
        data = {}
        humidity_control = HumidityControlCapabilities(data)
        assert humidity_control.humidification is None
        assert humidity_control.dehumidification is None


class TestCapabilities:
    """Test cases for Capabilities class."""

    def test_capabilities_with_empty_data(self):
        """Test Capabilities with empty data."""
        data = {}
        capabilities = Capabilities(data)
        assert capabilities.continuous_backlight is False
        assert capabilities.display_humidity is False
        assert capabilities.display_time is False
        assert capabilities.degrees_fc is False
        assert capabilities.keypad_lockout is False
        assert capabilities.max_cool_setpoint == MAX_COOL_SETPOINT
        assert capabilities.min_cool_setpoint == MIN_COOL_SETPOINT
        assert capabilities.max_heat_setpoint == MAX_HEAT_SETPOINT
        assert capabilities.min_heat_setpoint == MIN_HEAT_SETPOINT

    def test_capabilities_with_custom_setpoints(self):
        """Test Capabilities with custom setpoint values."""
        data = {
            "max_cool_setpoint": 88,
            "min_cool_setpoint": 50,
            "max_heat_setpoint": 95,
            "min_heat_setpoint": 55,
        }
        capabilities = Capabilities(data)
        assert capabilities.max_cool_setpoint == 88
        assert capabilities.min_cool_setpoint == 50
        assert capabilities.max_heat_setpoint == 95
        assert capabilities.min_heat_setpoint == 55

    def test_capabilities_with_operating_modes(self):
        """Test Capabilities with operating mode settings."""
        data = {
            "operating_mode_settings": {
                "off": "yes",
                "heat": "yes",
                "cool": "yes",
                "aux": "no",
                "auto": "yes",
            }
        }
        capabilities = Capabilities(data)
        assert capabilities.operating_mode_settings.off is True
        assert capabilities.operating_mode_settings.heat is True
        assert capabilities.operating_mode_settings.cool is True
        assert capabilities.operating_mode_settings.aux is False
        assert capabilities.operating_mode_settings.auto is True

    def test_capabilities_with_fan_modes(self):
        """Test Capabilities with fan mode settings."""
        data = {"fan_mode_settings": {"auto": "yes", "on": "yes", "smart": "no"}}
        capabilities = Capabilities(data)
        assert capabilities.fan_mode_settings.auto is True
        assert capabilities.fan_mode_settings.on is True
        assert capabilities.fan_mode_settings.smart is False

    def test_capabilities_with_circulating_fan(self):
        """Test Capabilities with circulating fan capabilities."""
        data = {
            "circulating_fan": {
                "capable": "yes",
                "max_duty_cycle": 100,
                "min_duty_cycle": 10,
                "step": 5,
            }
        }
        capabilities = Capabilities(data)
        assert capabilities.circulating_fan.capable is True
        assert capabilities.circulating_fan.max_duty_cycle == 100
        assert capabilities.circulating_fan.min_duty_cycle == 10
        assert capabilities.circulating_fan.step == 5

    def test_capabilities_with_humidity_control(self):
        """Test Capabilities with humidity control."""
        data = {
            "humidity_control": {
                "humidification": {
                    "step": 5,
                    "min": 5,
                    "max": 50,
                    "types": ["humidifier"],
                },
                "dehumidification": {
                    "step": 5,
                    "min": 40,
                    "max": 95,
                    "types": ["overcooling"],
                },
            }
        }
        capabilities = Capabilities(data)
        assert capabilities.humidity_control.humidification.min == 5
        assert capabilities.humidity_control.dehumidification.max == 95
