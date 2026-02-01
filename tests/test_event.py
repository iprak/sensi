"""Tests for Sensi event module."""

from custom_components.sensi.event import (
    BoolEventData,
    SetCirculatingFanEvent,
    SetCirculatingFanEventValue,
    SetFanModeEvent,
    SetHumidityEvent,
    SetHumidityEventValue,
    SetOperatingModeEvent,
    SetOperatingModeEventSuccess,
    SetTemperatureEvent,
    SetTemperatureEventSuccess,
)


def test_set_temperature_event_creation() -> None:
    """Test SetTemperatureEvent creation."""
    event = SetTemperatureEvent(
        icd_id="test_id",
        scale="f",
        mode="heat",
        target_temp=72.5,
    )

    assert event.icd_id == "test_id"
    assert event.scale == "f"
    assert event.mode == "heat"
    assert event.target_temp == 72.5


def test_set_temperature_event_success_creation() -> None:
    """Test SetTemperatureEventSuccess creation."""
    event = SetTemperatureEventSuccess(
        current_temp=70,
        mode="heat",
        target_temp=72,
    )

    assert event.current_temp == 70
    assert event.mode == "heat"
    assert event.target_temp == 72


class TestSetOperatingModeEvent:
    """Test cases for SetOperatingModeEvent dataclass."""

    def test_set_operating_mode_event_creation(self):
        """Test SetOperatingModeEvent creation."""
        event = SetOperatingModeEvent(
            icd_id="test_id",
            value="heat",
        )

        assert event.icd_id == "test_id"
        assert event.value == "heat"

    def test_set_operating_mode_event_different_modes(self):
        """Test SetOperatingModeEvent with different modes."""
        modes = ["heat", "cool", "auto", "off"]

        for mode in modes:
            event = SetOperatingModeEvent(icd_id="test_id", value=mode)
            assert event.value == mode


def test_set_operating_mode_event_success_creation() -> None:
    """Test SetOperatingModeEventSuccess creation."""
    event = SetOperatingModeEventSuccess(mode="heat")

    assert event.mode == "heat"


class TestSetCirculatingFanEventValue:
    """Test cases for SetCirculatingFanEventValue class."""

    def test_circulating_fan_event_value_enabled(self):
        """Test SetCirculatingFanEventValue with enabled fan."""
        value = SetCirculatingFanEventValue(enabled=True, duty_cycle=20)

        assert value.enabled == "on"
        assert value.duty_cycle == 20

    def test_circulating_fan_event_value_disabled(self):
        """Test SetCirculatingFanEventValue with disabled fan."""
        value = SetCirculatingFanEventValue(enabled=False, duty_cycle=0)

        assert value.enabled == "off"
        assert value.duty_cycle == 0

    def test_circulating_fan_event_value_various_duty_cycles(self):
        """Test SetCirculatingFanEventValue with various duty cycles."""
        duty_cycles = [5, 10, 25, 50, 100]

        for duty_cycle in duty_cycles:
            value = SetCirculatingFanEventValue(enabled=True, duty_cycle=duty_cycle)
            assert value.duty_cycle == duty_cycle
            assert value.enabled == "on"


def test_set_circulating_fan_event_creation() -> None:
    """Test SetCirculatingFanEvent creation."""
    fan_value = SetCirculatingFanEventValue(enabled=True, duty_cycle=15)
    event = SetCirculatingFanEvent(
        icd_id="test_id",
        value=fan_value,
    )

    assert event.icd_id == "test_id"
    assert event.value == fan_value
    assert event.value.enabled == "on"
    assert event.value.duty_cycle == 15


def test_set_fan_mode_event_creation() -> None:
    """Test SetFanModeEvent creation."""
    event = SetFanModeEvent(
        icd_id="test_id",
        value="auto",
    )

    assert event.icd_id == "test_id"
    assert event.value == "auto"


def test_bool_event_data() -> None:
    """Test BoolEventData."""
    event = BoolEventData(icd_id="test_id", value=True)

    assert event.icd_id == "test_id"
    assert event.value == "on"


class TestSetHumidityEventValue:
    """Test cases for SetHumidityEventValue class."""

    def test_humidity_event_value_enabled(self):
        """Test SetHumidityEventValue with enabled humidity."""
        value = SetHumidityEventValue(enabled=True, target_percent=40)

        assert value.enabled == "on"
        assert value.target_percent == 40

    def test_humidity_event_value_disabled(self):
        """Test SetHumidityEventValue with disabled humidity."""
        value = SetHumidityEventValue(enabled=False, target_percent=0)

        assert value.enabled == "off"
        assert value.target_percent == 0

    def test_humidity_event_value_various_percentages(self):
        """Test SetHumidityEventValue with various percentages."""
        percentages = [5, 20, 40, 50]

        for percent in percentages:
            value = SetHumidityEventValue(enabled=True, target_percent=percent)
            assert value.target_percent == percent
            assert value.enabled == "on"


def test_set_humidity_event_creation() -> None:
    """Test SetHumidityEvent creation."""
    humidity_value = SetHumidityEventValue(enabled=True, target_percent=35)
    event = SetHumidityEvent(
        icd_id="test_id",
        value=humidity_value,
    )

    assert event.icd_id == "test_id"
    assert event.value == humidity_value
    assert event.value.enabled == "on"
    assert event.value.target_percent == 35
