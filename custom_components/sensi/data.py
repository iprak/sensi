"""Data models for Sensi thermostats."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.util.enum import try_parse_enum

from .const import (
    COOL_MIN_TEMPERATURE,
    DEFAULT_HUMIDITY_STEP,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    HEAT_MAX_TEMPERATURE,
    LOGGER,
)
from .utils import to_bool


class OperatingMode(StrEnum):
    """Representation of Operating Modes."""

    OFF = "off"
    AUX = "aux"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"
    UNKNOWN = "unknown"


def get_hvac_mode_from_operating_mode(mode: OperatingMode) -> HVACMode:
    """Convert OperatingMode to HVACMode."""

    # Treating forced aux as Heating
    if mode in (OperatingMode.AUX, OperatingMode.HEAT):
        return HVACMode.HEAT

    if mode == OperatingMode.COOL:
        return HVACMode.COOL
    if mode == OperatingMode.AUTO:
        return HVACMode.AUTO
    if mode == OperatingMode.OFF:
        return HVACMode.OFF

    return None


def get_operating_mode_from_hvac_mode(mode: HVACMode) -> OperatingMode | None:
    """Convert HVACMode to OperatingMode."""
    if mode == HVACMode.HEAT:
        return OperatingMode.HEAT
    if mode == HVACMode.COOL:
        return OperatingMode.COOL
    if mode == HVACMode.AUTO:
        return OperatingMode.AUTO
    if mode == HVACMode.OFF:
        return OperatingMode.OFF

    return None


class HumidityControlStatus(StrEnum):
    """Control status for humidity control."""

    HUMIDIFYING = "humidifying"
    DEHUMIDIFYING = "dehumidifying"
    OVERCOOLING = "overcooling"
    OVERCOOLED = "overcooled"
    NONE = "none"


class FanMode(StrEnum):
    """Representation of Fan Modes."""

    ON = "on"
    AUTO = "auto"
    SMART = "smart"
    UNKNOWN = "unknown"


class DehumidificationMode(StrEnum):
    """Control status for humidity control."""

    OPTIMAL_DEHUMIDIFICATION = "overcooling"
    OPTIMAL_COMFORT = "fan_speed"
    HUMIDIFIER = "humidifier"
    UNKNOWN = "unknown"


@dataclass
class AuthenticationConfig:
    """Internal Sensi authentication configuration."""

    user_id: str | None = None
    access_token: str | None = None
    expires_at: float | None = None
    refresh_token: str | None = None

    @property
    def headers(self):
        """Get request headers."""
        return {"Authorization": "bearer " + self.access_token}


class CirculatingFan:
    """Representation of circulating fan status."""

    enabled: bool
    duty_cycle: int

    def __init__(self, data: dict) -> None:
        """Initialize CirculatingFan from data dictionary."""
        self.enabled = to_bool(data.get("enabled", ""))
        self.duty_cycle = data.get("duty_cycle", 0)


class DemandStatus:
    """Representation of runtime demand status for HVAC."""

    heat: int
    fan: int
    cool: int
    aux: int
    last: str
    last_start: int | None

    def __init__(self, data: dict) -> None:
        """Initialize DemandStatus from data dictionary."""

        self.heat = data.get("heat", 0)
        self.fan = data.get("fan", 0)
        self.cool = data.get("cool", 0)
        self.aux = data.get("aux", 0)
        self.last = data.get("last", "")
        self.last_start = data.get("last_start")


class Humidity:
    """Representation of humidification and dehumidification settings."""

    def __init__(self, data: dict) -> None:
        """Initialize humidification settings."""
        self.target_percent = data.get("target_percent", DEFAULT_MIN_HUMIDITY)
        self.enabled = data.get("enabled", "off") == "on"
        self.status = try_parse_enum(
            DehumidificationMode, data.get("mode", "humidifier")
        )

    def __repr__(self):
        """Return the representation."""
        return f"Humidity(target_percent={self.target_percent}, enabled={self.enabled}, status={self.status})"


class HumidityControl:
    """Representation of humidity control settings."""

    def __init__(self, data: dict) -> None:
        """Initialize humidity control settings."""
        # {'humidification': {'target_percent': 5, 'enabled': 'off', 'mode': 'humidifier'}, 'dehumidification': {'target_percent': 40, 'enabled': 'off', 'mode': 'overcooling'}, 'status': 'none'}

        self.humidification = Humidity(data.get("humidification", {}))
        self.dehumidification = Humidity(data.get("dehumidification", {}))
        self.status = try_parse_enum(HumidityControlStatus, data.get("status", "none"))


class State:
    """Thermostat state."""

    # "state":{"status":"online","current_cool_temp":76,"current_heat_temp":68,"display_temp":68.5,"current_operating_mode":"heat","humidity":89,"battery_voltage":2.956,"power_status":"c_wire","wifi_connection_quality":55,
    # "periodicity":0,"comfort_alert":null,"other_error_bitfield":{"bad_temperature_sensor":"off","bad_humidity_sensor":"off","stuck_key":"off","high_voltage":"off","e5_alert":"off","error_32":"off","error_64":"off"},
    # "current_humidification_percent":5,"current_dehumidification_percent":40,"relay_status":{"w":"off","w2":"off","g":"off","y":"off","y2":"off","o_b":"off"},
    # "demand_status":{"heat":0,"fan":0,"cool":0,"aux":0,"last":"heat","last_start":null,"cool_stage":null,"heat_stage":null,"aux_stage":null,"humidification":0,"dehumidification":0,"overcooling":"no"},
    # "hashedSchedule":"e1207cd23f7cedd8e53bfd4ce0e8881388efb0c0","current_off_temp":60,"display_scale":"f","heat_max_temp":77,"cool_min_temp":75,"hold_mode":"off","operating_mode":"heat","scheduling":"off","fan_mode":"auto",
    # "display_humidity":"on","continuous_backlight":"off","compressor_lockout":"on","early_start":"off","keypad_lockout":"off","temp_offset":0,"aux_cycle_rate":"medium","cool_cycle_rate":"medium","heat_cycle_rate":"medium",
    # "aux_boost":"on","heat_boost":"off","cool_boost":"off","dst_offset":60,"dst_observed":"yes","tz_offset":-360,"hold_end":null,"deadband":2,"display_time":"on","circulating_fan":{"enabled":"on","duty_cycle":10},
    # "humidity_offset":0,"partial_keypad_lockout":{"setpoint":"on","system_mode":"on","fan_mode":"on","schedule_mode":"on","settings_menu":"on"},
    # "humidity_control":{"humidification":{"target_percent":5,"enabled":"off","mode":"humidifier"},"dehumidification":{"target_percent":40,"enabled":"off","mode":"overcooling"},"status":"none"},"lcd_sleep_mode":null,
    # "night_light":null,"outdoor_weather_display":"ff:00:00:ff:ff:ff:00:00:ff:00:00:ff:00:00:ff:00:00:ff:00","geofencing":null,"remote_sensor_status":"00","target_off_temp":60,
    # "control":{"mode":"off","devices":null,"geo_state":null,"device_data":null}}}]]
    battery_voltage: float
    circulating_fan: CirculatingFan
    continuous_backlight: bool
    cool_min_temp: int
    current_cool_temp: int
    current_heat_temp: int
    demand_status: DemandStatus
    display_humidity: bool

    display_scale: str
    """Use temperature_unit instead."""

    display_temp: float
    display_time: bool
    fan_mode: FanMode
    heat_max_temp: int
    humidity: int
    humidity_control: HumidityControl
    humidity_offset: int
    keypad_lockout: bool
    operating_mode: OperatingMode
    power_status: str
    status: str
    temp_offset: int
    wifi_connection_quality: int

    def __init__(self, data: dict) -> None:
        """Initialize State from data dictionary."""
        self.battery_voltage = data.get("battery_voltage", 0.0)
        self.circulating_fan = CirculatingFan(data.get("circulating_fan", {}))
        self.continuous_backlight = to_bool(data.get("continuous_backlight", ""))
        self.cool_min_temp = data.get("cool_min_temp", COOL_MIN_TEMPERATURE)
        self.current_cool_temp = data.get("current_cool_temp", 0)
        self.current_heat_temp = data.get("current_heat_temp", 0)

        self.demand_status = DemandStatus(
            data.get("demand_status", {})
        )  # Demand status contains runtime power/demand values for HVAC

        self.display_humidity = to_bool(data.get("display_humidity", ""))
        self.display_scale = data.get("display_scale", "")
        self.display_temp = data.get("display_temp", 0.0)
        self.display_time = to_bool(data.get("display_time", ""))
        self.fan_mode = try_parse_enum(FanMode, data.get("fan_mode", FanMode.UNKNOWN))
        self.heat_max_temp = data.get("heat_max_temp", HEAT_MAX_TEMPERATURE)
        self.humidity = data.get("humidity", 0)
        self.humidity_control = HumidityControl(data.get("humidity_control", {}))
        self.humidity_offset = data.get("humidity_offset", 0)
        self.keypad_lockout = to_bool(data.get("keypad_lockout", ""))
        self.operating_mode = try_parse_enum(
            OperatingMode, data.get("operating_mode", OperatingMode.UNKNOWN)
        )
        self.power_status = data.get("power_status", "")
        self.status = data.get("status", "")
        self.temp_offset = data.get("temp_offset", 0)
        self.wifi_connection_quality = data.get("wifi_connection_quality", 0)

        self.temperature_unit = (
            UnitOfTemperature.CELSIUS
            if self.display_scale == "c"
            else UnitOfTemperature.FAHRENHEIT
        )

    def __str__(self):
        """Return string representation of State."""
        return (
            f"State(status={self.status}, operating_mode={self.operating_mode}, "
            f"display_temp={self.display_temp}{self.temperature_unit}, "
            f"humidity={self.humidity}%"
        )


class Firmware:
    """Thermostat firmware information."""

    firmware_version: str
    bootloader_version: str
    wifi_version: str

    def __init__(self, data: dict) -> None:
        """Initialize FirmwareInfo from data dictionary."""
        self.firmware_version = data.get("firmware_version", "")
        self.bootloader_version = data.get("bootloader_version", "")
        self.wifi_version = data.get("wifi_version", "")


class ThermostatInfo:
    """Thermostat information returned from Sensi websocket."""

    test_date: str
    build_date: str
    serial_number: str
    model_number: str
    unique_hardware_id: str
    wifi_mac_address: str
    images: Firmware
    last_changed_timestamp: int

    def __init__(self, data: dict) -> None:
        """Initialize ThermostatInfo from data dictionary."""
        # {'test_date': '11/14/2018', 'build_date': '11/14/2018', 'serial_number': '42WFRP46B00220', 'unique_hardware_id': 1, 'model_number': '1F87U-42WFC', 'images': {'bootloader_version': '6003970905', 'firmware_version': '6004850907', 'wifi_version': '6004820907'}, 'wifi_mac_address': '346F920C0B07', 'last_changed_timestamp': 1759918908}

        self.test_date = data.get("test_date", "")
        self.build_date = data.get("build_date", "")
        self.serial_number = data.get("serial_number", "")
        self.model_number = data.get("model_number", "")
        self.unique_hardware_id = data.get("unique_hardware_id", "")
        self.wifi_mac_address = data.get("wifi_mac_address", "")
        self.images = Firmware(data.get("images", {}))
        self.last_changed_timestamp = data.get("last_changed_timestamp", 0)

    def __str__(self):
        """Return string representation of ThermostatInfo."""
        return (
            f"ThermostatInfo(model={self.model_number}, serial={self.serial_number}, "
            f"hw_id={self.unique_hardware_id}, wifi_mac={self.wifi_mac_address}"
        )


class SystemModes:
    """Representation of System modes capabilities."""

    off: bool
    heat: bool
    cool: bool
    aux: bool
    auto: bool

    def __init__(self, data: dict) -> None:
        """Initialize SystemModes from data dictionary."""
        self.off = to_bool(data.get("off", "no"))
        self.heat = to_bool(data.get("heat", "no"))
        self.cool = to_bool(data.get("cool", "no"))
        self.aux = to_bool(data.get("aux", "no"))
        self.auto = to_bool(data.get("auto", "no"))


class CirculatingFanCapabilities:
    """Representation of Circulating Fan capabilities."""

    capable: bool
    max_duty_cycle: int
    min_duty_cycle: int
    step: int

    def __init__(self, data: dict) -> None:
        """Initialize CirculatingFanCapabilities from data dictionary."""
        self.capable = to_bool(data.get("capable", "no"))
        self.max_duty_cycle = data.get("max_duty_cycle", 0)
        self.min_duty_cycle = data.get("min_duty_cycle", 0)
        self.step = data.get("step", 0)


class FanModes:
    """Representation of Fan modes capabilities."""

    auto: bool
    on: bool
    smart: bool

    def __init__(self, data: dict) -> None:
        """Initialize FanModes from data dictionary."""
        self.auto = to_bool(data.get("auto", "no"))
        self.on = to_bool(data.get("on", "no"))
        self.smart = to_bool(data.get("smart", "no"))


class HumidityCapabilities:
    """Representation of humidification capabilities."""

    max: int
    min: int
    step: int
    types: list[any]

    def __init__(self, data: dict) -> None:
        """Initialize Capabilities from data dictionary."""
        self.max = data.get("max", DEFAULT_MIN_HUMIDITY)
        self.min = data.get("min", DEFAULT_MAX_HUMIDITY)
        self.step = data.get("step", DEFAULT_HUMIDITY_STEP)
        self.types = data.get("types", [])


class HumidityControlCapabilities:
    """Representation of humidification control capabilities."""

    humidification: HumidityCapabilities
    dehumidification: HumidityCapabilities

    def __init__(self, data: dict) -> None:
        """Initialize Capabilities from data dictionary."""
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
    circulating_fan: CirculatingFanCapabilities
    continuous_backlight: bool
    degrees_fc: bool
    display_humidity: bool
    display_outdoor_temp: bool
    display_time: bool
    fan_mode_settings: FanModes
    humidity_control: HumidityControlCapabilities
    keypad_lockout: bool
    max_cool_setpoint: int
    max_heat_setpoint: int
    min_cool_setpoint: int
    min_heat_setpoint: int
    operating_mode_settings: SystemModes

    def __init__(self, data: dict) -> None:
        """Initialize Capabilities from data dictionary."""
        self.circulating_fan = CirculatingFanCapabilities(
            data.get("circulating_fan", {})
        )
        self.continuous_backlight = to_bool(data.get("continuous_backlight", "no"))
        self.degrees_fc = to_bool(data.get("degrees_fc", "no"))
        self.display_humidity = to_bool(data.get("display_humidity", "no"))
        self.display_outdoor_temp = to_bool(data.get("display_outdoor_temp", "no"))
        self.display_time = to_bool(data.get("display_time", "no"))
        self.fan_mode_settings = FanModes(data.get("fan_mode_settings", {}))
        self.humidity_control = HumidityControlCapabilities(
            data.get("humidity_control", {})
        )
        self.keypad_lockout = to_bool(data.get("keypad_lockout", "no"))
        self.max_cool_setpoint = data.get(
            "max_cool_setpoint", 85
        )  # Default limits based on the app
        self.max_heat_setpoint = data.get("max_heat_setpoint", 99)
        self.min_cool_setpoint = data.get("min_cool_setpoint", 45)
        self.min_heat_setpoint = data.get("min_heat_setpoint", 60)
        self.operating_mode_settings = SystemModes(
            data.get("operating_mode_settings", {})
        )

    def __str__(self):
        """Return string representation of Capabilities."""
        return (
            f"Capabilities(heat_range={self.min_heat_setpoint}-{self.max_heat_setpoint}, "
            f"cool_range={self.min_cool_setpoint}-{self.max_cool_setpoint}, "
            f"modes={self.operating_mode_settings.__dict__}, "
            f"backlight={self.continuous_backlight}, "
            f"keypad_lock={self.keypad_lockout})"
        )


class SensiDevice:
    """Representation of a Sensi thermostat."""

    identifier: str
    name: str
    state: State
    capabilities: Capabilities
    info: ThermostatInfo

    def __init__(
        self,
        identifier: str,
        registration: dict,
        capabilities: dict,
        info: dict,
        state: dict,
    ) -> None:
        """Initialize Thermostat from data values."""

        # ["state",[{"icd_id":"36-6f-92-ff-fe-0c-0b-07",
        # "registration":{"city":"Madison","name":"Living Room","state":"Wisconsin","country":"US","address1":"Somewhere","address2":null,"timezone":"America/Chicago","postal_code":"53719","product_type":"Sensi Classic with HomeKit","contractor_id":null,"fleet_enabled":false,"fleet_enabled_date":null},

        self.capabilities = Capabilities(capabilities)
        self.identifier = identifier
        self.info = ThermostatInfo(info)
        self.name = registration.get("name", "")
        self.state = State(state)

        LOGGER.debug(f"{self.identifier} Capabilities={self.capabilities}")
        LOGGER.debug(f"{self.identifier} Info={self.info}")
        LOGGER.debug(f"{self.identifier} State={self.state}")

    @classmethod
    def create(cls, data: any) -> tuple[bool, Self]:
        """Create a SensiDevice instance from data dictionary.

        Returns a tuple of (have_state, SensiDevice).
        """
        identifier = data.get("icd_id", "")

        registration = data.get("registration", {})
        capabilities = data.get("capabilities", {})
        info = data.get("thermostat_info", {})
        state = data.get("state", {})

        have_state = bool(state)
        return (
            have_state,
            SensiDevice(identifier, registration, capabilities, info, state),
        )

    def update_state(self, data: dict) -> bool:
        """Update the thermostat state from data dictionary."""
        source = data.get("state")
        if source:
            self.state = State(source)
            LOGGER.debug(f"{self.identifier} State updated to {self.state}")
            return True

        return False

    def update_capabilities(self, source: dict) -> None:
        """Update the thermostat capabilities from data dictionary."""
        if source:
            self.capabilities = Capabilities(source)

    def update_info(self, source: dict) -> None:
        """Update the thermostat info from data dictionary."""
        if source:
            self.info = ThermostatInfo(source)
