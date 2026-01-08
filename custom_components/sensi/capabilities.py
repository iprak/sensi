"""Data models for Sensi thermostats."""

from typing import Final

from .const import DEFAULT_HUMIDITY_STEP, DEFAULT_MAX_HUMIDITY, DEFAULT_MIN_HUMIDITY
from .utils import to_bool, to_int

# Default limits based on the app
MAX_COOL_SETPOINT: Final = 85
MIN_COOL_SETPOINT: Final = 45
MAX_HEAT_SETPOINT: Final = 99
MIN_HEAT_SETPOINT: Final = 60


class SystemModes:
    """Representation of System modes capabilities."""

    def __init__(self, data: dict) -> None:
        """Initialize SystemModes from data dictionary."""
        self.off = to_bool(data.get("off"))
        self.heat = to_bool(data.get("heat"))
        self.cool = to_bool(data.get("cool"))
        self.aux = to_bool(data.get("aux"))
        self.auto = to_bool(data.get("auto"))


class CirculatingFanCapabilities:
    """Representation of Circulating Fan capabilities."""

    def __init__(self, data: dict) -> None:
        """Initialize CirculatingFanCapabilities from data dictionary."""

        # "circulating_fan":{"capable":"yes","max_duty_cycle":100,"min_duty_cycle":10,"step":5}
        self.capable = to_bool(data.get("capable"))
        self.max_duty_cycle = to_int(data.get("max_duty_cycle"), 0)
        self.min_duty_cycle = to_int(data.get("min_duty_cycle"), 0)
        self.step = to_int(data.get("step"), 0)


class FanModes:
    """Representation of Fan modes capabilities."""

    def __init__(self, data: dict) -> None:
        """Initialize FanModes from data dictionary."""

        # "fan_mode_settings":{"auto":"yes","on":"yes","smart":"no"}
        self.auto = to_bool(data.get("auto"))
        self.on = to_bool(data.get("on"))
        self.smart = to_bool(data.get("smart"))


class HumidityCapabilities:
    """Representation of humidification capabilities."""

    def __init__(self, data: dict) -> None:
        """Initialize HumidityCapabilities from data dictionary."""

        # "humidification":{"step":5,"min":5,"max":50,"types":["humidifier"]},"dehumidification":{"step":5,"min":40,"max":95,"types":["overcooling"]}
        self.max = to_int(data.get("max"), DEFAULT_MIN_HUMIDITY)
        self.min = to_int(data.get("min"), DEFAULT_MAX_HUMIDITY)
        self.step = to_int(data.get("step"), DEFAULT_HUMIDITY_STEP)
        self.types = data.get("types", [])


class HumidityControlCapabilities:
    """Representation of humidification control capabilities."""

    def __init__(self, data: dict) -> None:
        """Initialize HumidityControlCapabilities from data dictionary."""
        self.humidification = HumidityCapabilities(data.get("humidification", {}))
        self.dehumidification = HumidityCapabilities(data.get("dehumidification", {}))


class Capabilities:
    """Representation of Thermostat capabilities."""

    # {'last_changed_timestamp': 1756195713, 'early_start': 'yes',
    # 'boost': {'aux': 'no', 'cool': 'yes', 'heat': 'yes'}, 'aux_cycle_rate': 'no', 'cool_cycle_rate': 'yes', 'heat_cycle_rate': 'yes', 'dual_fuel_outdoor_temperature_setpoint': 'no',
    # 'compressor_lockout': 'yes', 'aux_cycle_rate_steps': ['slow', 'medium', 'fast'], 'cool_cycle_rate_steps': ['slow', 'medium', 'fast'], 'heat_cycle_rate_steps': ['slow', 'medium', 'fast'],
    #  'keypad_lockout': 'yes', 'continuous_backlight': 'yes', 'degrees_fc': 'yes', 'temp_offset': 'yes', 'humidity_offset': 'yes', 'display_humidity': 'yes', 'display_outdoor_temp': 'yes',
    # 'display_time': 'yes', 'temp_offset_lower_bound': -5, 'temp_offset_upper_bound': 5, 'humidity_offset_lower_bound': -25, 'humidity_offset_upper_bound': 25, 'min_heat_setpoint': 45,
    # 'min_cool_setpoint': 45, 'max_heat_setpoint': 99, 'max_cool_setpoint': 99, 'heat_setpoint_ceiling': 'yes', 'cool_setpoint_floor': 'yes', 'lowest_heat_setpoint_ceiling': 60,
    # 'highest_cool_setpoint_floor': 85, 'scheduling': 'yes', 'max_steps_per_day': 8, 'days_per_schedule': 7,
    # 'hold_modes': {'temporary': 'yes', 'permanent': 'no', 'curtailment': 'no'},
    #  'circulating_fan': {'capable': 'yes', 'max_duty_cycle': 100, 'min_duty_cycle': 10, 'step': 5},
    # 'partial_keypad_lockout': {'setpoint': 'yes', 'system_mode': 'yes', 'fan_mode': 'yes', 'schedule_mode': 'yes', 'settings_menu': 'yes'},
    # 'indoor_equipment': 'electric', 'outdoor_equipment': 'ac', 'indoor_stages': 2, 'outdoor_stages': 2, 'fan_stages': 0, 'out_of_box_configuration': 'no',
    # 'reversing_valve_mode': 'O', 'operating_mode_settings': {'off': 'yes', 'heat': 'yes', 'cool': 'yes', 'aux': 'no', 'auto': 'yes'},
    #  'fan_mode_settings': {'auto': 'yes', 'on': 'yes', 'smart': 'no'},
    # 'eim_control_capable': 'no', 'contractor_info': 'no',
    # 'humidity_control': {'deadband': 10, 'humidification': {'step': 5, 'min': 5, 'max': 50, 'types': []}, 'dehumidification': {'step': 5, 'min': 40, 'max': 95, 'types': ['overcooling']}},
    # 'open_adr': {'demand_response': 'yes', 'direct_load_controls': 'no', 'use_of_pricing': 'yes'}}

    def __init__(self, data: dict) -> None:
        """Initialize Capabilities from data dictionary."""

        self.circulating_fan = CirculatingFanCapabilities(
            data.get("circulating_fan", {})
        )
        self.continuous_backlight = to_bool(data.get("continuous_backlight"))
        self.degrees_fc = to_bool(data.get("degrees_fc"))
        self.display_humidity = to_bool(data.get("display_humidity"))
        self.display_time = to_bool(data.get("display_time"))
        self.fan_mode_settings = FanModes(data.get("fan_mode_settings", {}))
        self.humidity_control = HumidityControlCapabilities(
            data.get("humidity_control", {})
        )
        self.keypad_lockout = to_bool(data.get("keypad_lockout"))
        self.max_cool_setpoint = to_int(
            data.get("max_cool_setpoint"), MAX_COOL_SETPOINT
        )
        self.max_heat_setpoint = to_int(
            data.get("max_heat_setpoint"), MAX_HEAT_SETPOINT
        )
        self.min_cool_setpoint = to_int(
            data.get("min_cool_setpoint"), MIN_COOL_SETPOINT
        )
        self.min_heat_setpoint = to_int(
            data.get("min_heat_setpoint"), MIN_HEAT_SETPOINT
        )
        self.operating_mode_settings = SystemModes(
            data.get("operating_mode_settings", {})
        )

    def __str__(self):
        """Return string representation of Capabilities."""
        return (
            f"Capabilities(heat_range={self.min_heat_setpoint}-{self.max_heat_setpoint}, "
            f"cool_range={self.min_cool_setpoint}-{self.max_cool_setpoint}, "
            f"modes={self.operating_mode_settings.__dict__}, "
            f"backlight={self.continuous_backlight}"
        )
