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
    SettingEventName,
)


class TestSettingEventName:
    """Test cases for SettingEventName enum."""

    def test_display_time_event_name(self):
        """Test DISPLAY_TIME event name."""
        assert SettingEventName.DISPLAY_TIME == "set_display_time"

    def test_display_humidity_event_name(self):
        """Test DISPLAY_HUMIDITY event name."""
        assert SettingEventName.DISPLAY_HUMIDITY == "set_display_humidity"

    def test_continuous_backlight_event_name(self):
        """Test CONTINUOUS_BACKLIGHT event name."""
        assert SettingEventName.CONTINUOUS_BACKLIGHT == "set_continuous_backlight"

    def test_keypad_lockout_event_name(self):
        """Test KEYPAD_LOCKOUT event name."""
        assert SettingEventName.KEYPAD_LOCKOUT == "set_keypad_lockout"

    def test_heat_boost_event_name(self):
        """Test HEAT_BOOST event name."""
        assert SettingEventName.HEAT_BOOST == "set_heat_boost"

    def test_cool_boost_event_name(self):
        """Test COOL_BOOST event name."""
        assert SettingEventName.COOL_BOOST == "set_cool_boost"

    def test_aux_boost_event_name(self):
        """Test AUX_BOOST event name."""
        assert SettingEventName.AUX_BOOST == "set_aux_boost"

    def test_ac_protection_event_name(self):
        """Test AC_PROTECTION event name."""
        assert SettingEventName.AC_PROTECTION == "set_compressor_lockout"

    def test_early_start_event_name(self):
        """Test EARLY_START event name."""
        assert SettingEventName.EARLY_START == "set_early_start"

    def test_circulating_fan_event_name(self):
        """Test CIRCULATING_FAN event name."""
        assert SettingEventName.CIRCULATING_FAN == "set_circulating_fan"

    def test_heat_max_temp_event_name(self):
        """Test HEAT_MAX_TEMP event name."""
        assert SettingEventName.HEAT_MAX_TEMP == "set_heat_max_temp"

    def test_cool_min_temp_event_name(self):
        """Test COOL_MIN_TEMP event name."""
        assert SettingEventName.COOL_MIN_TEMP == "set_cool_min_temp"


class TestSetTemperatureEvent:
    """Test cases for SetTemperatureEvent dataclass."""

    def test_set_temperature_event_creation(self):
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

    def test_set_temperature_event_with_celsius(self):
        """Test SetTemperatureEvent with Celsius scale."""
        event = SetTemperatureEvent(
            icd_id="test_id",
            scale="c",
            mode="cool",
            target_temp=22.0,
        )

        assert event.scale == "c"
        assert event.target_temp == 22.0


class TestSetTemperatureEventSuccess:
    """Test cases for SetTemperatureEventSuccess dataclass."""

    def test_set_temperature_event_success_creation(self):
        """Test SetTemperatureEventSuccess creation."""
        event = SetTemperatureEventSuccess(
            current_temp=70,
            mode="heat",
            target_temp=72,
        )

        assert event.current_temp == 70
        assert event.mode == "heat"
        assert event.target_temp == 72

    def test_set_temperature_event_success_different_values(self):
        """Test SetTemperatureEventSuccess with different values."""
        event = SetTemperatureEventSuccess(
            current_temp=75,
            mode="cool",
            target_temp=74,
        )

        assert event.current_temp == 75
        assert event.mode == "cool"
        assert event.target_temp == 74


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


class TestSetOperatingModeEventSuccess:
    """Test cases for SetOperatingModeEventSuccess dataclass."""

    def test_set_operating_mode_event_success_creation(self):
        """Test SetOperatingModeEventSuccess creation."""
        event = SetOperatingModeEventSuccess(mode="heat")

        assert event.mode == "heat"

    def test_set_operating_mode_event_success_cool_mode(self):
        """Test SetOperatingModeEventSuccess with cool mode."""
        event = SetOperatingModeEventSuccess(mode="cool")

        assert event.mode == "cool"


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


class TestSetCirculatingFanEvent:
    """Test cases for SetCirculatingFanEvent dataclass."""

    def test_set_circulating_fan_event_creation(self):
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

    def test_set_circulating_fan_event_disabled(self):
        """Test SetCirculatingFanEvent with disabled fan."""
        fan_value = SetCirculatingFanEventValue(enabled=False, duty_cycle=0)
        event = SetCirculatingFanEvent(
            icd_id="test_id",
            value=fan_value,
        )

        assert event.value.enabled == "off"


class TestSetFanModeEvent:
    """Test cases for SetFanModeEvent dataclass."""

    def test_set_fan_mode_event_creation(self):
        """Test SetFanModeEvent creation."""
        event = SetFanModeEvent(
            icd_id="test_id",
            value="auto",
        )

        assert event.icd_id == "test_id"
        assert event.value == "auto"

    def test_set_fan_mode_event_different_modes(self):
        """Test SetFanModeEvent with different fan modes."""
        modes = ["auto", "on", "circulate"]

        for mode in modes:
            event = SetFanModeEvent(icd_id="test_id", value=mode)
            assert event.value == mode


class TestBoolEventData:
    """Test cases for BoolEventData class."""

    def test_bool_event_data_true(self):
        """Test BoolEventData with True value."""
        event = BoolEventData(icd_id="test_id", value=True)

        assert event.icd_id == "test_id"
        assert event.value == "on"

    def test_bool_event_data_false(self):
        """Test BoolEventData with False value."""
        event = BoolEventData(icd_id="test_id", value=False)

        assert event.icd_id == "test_id"
        assert event.value == "off"

    def test_bool_event_data_multiple_ids(self):
        """Test BoolEventData with different IDs."""
        event1 = BoolEventData(icd_id="id1", value=True)
        event2 = BoolEventData(icd_id="id2", value=False)

        assert event1.icd_id == "id1"
        assert event2.icd_id == "id2"
        assert event1.value == "on"
        assert event2.value == "off"


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


class TestSetHumidityEvent:
    """Test cases for SetHumidityEvent dataclass."""

    def test_set_humidity_event_creation(self):
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

    def test_set_humidity_event_disabled(self):
        """Test SetHumidityEvent with disabled humidity."""
        humidity_value = SetHumidityEventValue(enabled=False, target_percent=0)
        event = SetHumidityEvent(
            icd_id="test_id",
            value=humidity_value,
        )

        assert event.value.enabled == "off"
