"""Event data models for Sensi thermostats."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .utils import bool_to_onoff


class SettingEventName(StrEnum):
    """Thermostat properties."""

    DISPLAY_TIME = "set_display_time"
    DISPLAY_HUMIDITY = "set_display_humidity"
    CONTINUOUS_BACKLIGHT = "set_continuous_backlight"
    KEYPAD_LOCKOUT = "set_keypad_lockout"
    HEAT_BOOST = "set_heat_boost"
    COOL_BOOST = "set_cool_boost"
    AUX_BOOST = "set_aux_boost"
    AC_PROTECTION = "set_compressor_lockout"
    EARLY_START = "set_early_start"
    CIRCULATING_FAN = "set_circulating_fan"
    HEAT_MAX_TEMP = "set_heat_max_temp"
    COOL_MIN_TEMP = "set_cool_min_temp"


@dataclass
class SetTemperatureEvent:
    """Data for set_temperature event."""

    icd_id: str
    scale: str
    mode: str
    target_temp: float


@dataclass
class SetTemperatureEventSuccess:
    """Success data for set_temperature event."""

    current_temp: int
    mode: str
    target_temp: int


@dataclass
class SetOperatingModeEvent:
    """Data for set_operating_mode event."""

    icd_id: str
    value: str


@dataclass
class SetOperatingModeEventSuccess:
    """Success data for set_operating_mode event."""

    mode: str


class SetCirculatingFanEventValue:
    """Data for set_circulating_fan event."""

    enabled: str
    duty_cycle: int

    def __init__(self, enabled: bool, duty_cycle: int) -> None:
        """Create an instance of SetCirculatingFanEventValue."""
        self.enabled = bool_to_onoff(enabled)
        self.duty_cycle = duty_cycle


@dataclass
class SetCirculatingFanEvent:
    """Data for set_circulating_fan event."""

    icd_id: str
    value: SetCirculatingFanEventValue


@dataclass
class SetFanModeEvent:
    """Data for set_fan_mode event."""

    icd_id: str
    value: str


@dataclass
class BoolEventData:
    """Data for bool setting event."""

    icd_id: str
    value: str

    def __init__(self, icd_id: str, value: bool) -> None:
        """Create an instance of SetCirculatingFanEventValue."""
        self.icd_id = icd_id
        self.value = bool_to_onoff(value)


@dataclass
class SetHumidityEventValue:
    """Data for set_temperature event."""

    enabled: str
    target_percent: int

    def __init__(self, enabled: bool, target_percent: int) -> None:
        """Create an instance of SetHumidityEventValue."""
        self.enabled = bool_to_onoff(enabled)
        self.target_percent = target_percent


@dataclass
class SetHumidityEvent:
    """Data for set_humidification event."""

    icd_id: str
    value: SetHumidityEventValue


# get_settings
# {"display_scale":"f","heat_max_temp":77,"cool_min_temp":75,"hold_mode":"off","operating_mode":"heat","scheduling":"off","fan_mode":"auto",
# "display_humidity":"on","continuous_backlight":"off","compressor_lockout":"on","early_start":"off","keypad_lockout":"off","temp_offset":0,
# "aux_cycle_rate":"medium","cool_cycle_rate":"medium","heat_cycle_rate":"medium","aux_boost":"on","heat_boost":"off","cool_boost":"off",
# "dst_offset":60,"dst_observed":"yes","tz_offset":-360,"hold_end":null,"deadband":2,"display_time":"on",
# "circulating_fan":{"enabled":"on","duty_cycle":10},"humidity_offset":0,
# "partial_keypad_lockout":{"setpoint":"on","system_mode":"on","fan_mode":"on","schedule_mode":"on","settings_menu":"on"},
# "humidity_control":{"humidification":{"target_percent":5,"enabled":"off","mode":"humidifier"},
# "dehumidification":{"target_percent":40,"enabled":"off","mode":"overcooling"},"status":"none"},"lcd_sleep_mode":null,"night_light":null,
# "outdoor_weather_display":"ff:00:00:ff:ff:ff:00:00:ff:00:00:ff:00:00:ff:00:00:ff:00","geofencing":null,"remote_sensor_status":"00","target_off_temp":60}]
