"""Data models for Sensi thermostats."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from typing import Self

from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.util.enum import try_parse_enum

from .capabilities import Capabilities
from .const import (
    DEFAULT_MIN_HUMIDITY,
    LOGGER,
    TEMPERATURE_LOWER_LIMIT,
    TEMPERATURE_UPPER_LIMIT,
)
from .utils import to_bool, to_float, to_int


def _first_value(source: dict[str, Any] | None, *keys: str) -> Any:
    """Return the first defined value for the given keys."""
    if not source:
        return None

    for key in keys:
        if key in source and source[key] is not None:
            return source[key]

    return None


def _nested_value(
    source: dict[str, Any] | None, keys: tuple[str, ...], nested_keys: tuple[str, ...]
) -> Any:
    """Return a direct or nested value from the given keys."""
    value = _first_value(source, *keys)
    if isinstance(value, dict):
        nested_value = _first_value(value, *nested_keys)
        if nested_value is not None:
            return nested_value

    return value


def _extract_optional_bool(source: dict[str, Any] | None, *keys: str) -> bool | None:
    """Extract an optional bool value."""
    value = _first_value(source, *keys)
    if value is None:
        return None

    return to_bool(value)


class RoomSensorStats:
    """Summary details for thermostat room sensors."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        """Initialize summary details from websocket or REST payloads."""
        data = data or {}

        self.active_control_group_id = to_int(
            _first_value(
                data,
                "active_control_group_id",
                "active_group_id",
                "group_id",
                "groupId",
                "selectedGroupId",
            ),
            None,
        )
        self.num_sensors = to_int(
            _first_value(data, "num_sensors", "numSensors"), None
        )
        self.num_participating_sensors = to_int(
            _first_value(
                data, "num_participating_sensors", "numParticipatingSensors"
            ),
            None,
        )

        errors = _first_value(
            data, "sensor_errors", "sensorErrors", "sensorsWithErrors"
        )
        self.sensor_errors = errors if isinstance(errors, list) else []
        self.raw = data

        sensors = data.get("sensors")
        if self.num_sensors is None and isinstance(sensors, list):
            self.num_sensors = len(sensors)

        if self.num_participating_sensors is None and isinstance(sensors, list):
            self.num_participating_sensors = len(
                [sensor for sensor in sensors if to_bool(sensor.get("active"))]
            )

    @property
    def has_data(self) -> bool:
        """Return true if any room sensor summary data was captured."""
        return bool(self.raw)


class RoomSensor:
    """Representation of an individual thermostat or remote room sensor."""

    def __init__(
        self,
        data: dict[str, Any],
        *,
        default_id: str | None = None,
        default_name: str | None = None,
        default_type: str | None = None,
    ) -> None:
        """Initialize room sensor details from REST payload data."""
        self.raw = data

        identifier = _first_value(data, "id", "sensor_id", "sensorId")
        self.identifier = str(identifier or default_id or "")

        name = _first_value(data, "name", "label", "display_name", "displayName")
        self.name = str(name or default_name or self.identifier or "Sensor")

        sensor_type = _first_value(data, "type", "sensor_type", "sensorType")
        self.sensor_type = str(sensor_type or default_type or "")

        self.temperature = to_float(
            _nested_value(
                data,
                ("temperature", "temp", "display_temp"),
                ("temperature", "temp", "value"),
            ),
            None,
        )
        self.humidity = to_int(
            _nested_value(
                data,
                ("humidity", "relative_humidity", "relativeHumidity"),
                ("humidity", "relativeHumidity", "value", "percent", "percentage"),
            ),
            None,
        )
        self.battery = to_int(
            _nested_value(
                data,
                ("battery", "battery_level", "batteryLevel", "battery_voltage"),
                ("value", "level", "percent", "percentage"),
            ),
            None,
        )
        self.battery_status = str(
            _first_value(data, "battery_voltage_enum", "battery_status", "batteryStatus")
            or ""
        )
        self.signal_strength = _nested_value(
            data,
            ("signal_strength", "signalStrength", "rssi"),
            ("value", "level"),
        )
        self.signal_strength_status = str(
            _first_value(
                data,
                "signal_strength_enum",
                "signalStrengthEnum",
                "signal_strength_status",
            )
            or ""
        )
        self.active = _extract_optional_bool(data, "active", "isActive")
        self.has_error = _extract_optional_bool(
            data,
            "has_error",
            "hasError",
            "sensor_error",
            "sensorError",
        )
        self.state = str(_first_value(data, "state", "status") or "")
        self.firmware_version = str(
            _first_value(data, "firmware_version", "firmwareVersion") or ""
        )

    def as_attributes(self) -> dict[str, Any]:
        """Return room sensor data in a Home Assistant friendly shape."""
        attrs = {
            "sensor_id": self.identifier,
            "name": self.name,
            "type": self.sensor_type,
            "active": self.active,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "battery": self.battery,
            "battery_status": self.battery_status or None,
            "signal_strength": self.signal_strength,
            "signal_strength_status": self.signal_strength_status or None,
            "has_error": self.has_error,
            "state": self.state or None,
            "firmware_version": self.firmware_version or None,
        }
        return {key: value for key, value in attrs.items() if value is not None}


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
    """Humidity control statuses."""

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
    """Humidification control mode."""

    OPTIMAL_DEHUMIDIFICATION = "overcooling"
    OPTIMAL_COMFORT = "fan_speed"
    HUMIDIFIER = "humidifier"
    UNKNOWN = "unknown"


@dataclass
class AuthenticationConfig:
    """Internal Sensi authentication configuration."""

    refresh_token: str
    user_id: str | None = None
    access_token: str | None = None
    expires_at: float | None = None

    @property
    def headers(self):
        """Get request headers."""
        return {"Authorization": "bearer " + self.access_token}


class CirculatingFan:
    """Representation of circulating fan status."""

    def __init__(self, data: dict) -> None:
        """Initialize CirculatingFan from data dictionary."""

        # "circulating_fan":{"enabled":"on","duty_cycle":10}
        self.enabled = to_bool(data.get("enabled"))
        self.duty_cycle = to_int(data.get("duty_cycle"), 0)


class DemandStatus:
    """Representation of runtime demand status for HVAC."""

    def __init__(self, data: dict) -> None:
        """Initialize DemandStatus from data dictionary."""

        # "demand_status":{"heat":0,"fan":0,"cool":0,"aux":0,"last":"heat","last_start":null,"cool_stage":null,"heat_stage":null,"aux_stage":null,"humidification":0,"dehumidification":0,"overcooling":"no"},
        self.heat = to_int(data.get("heat"), 0)
        self.fan = to_int(data.get("fan"), 0)
        self.cool = to_int(data.get("cool"), 0)
        self.aux = to_int(data.get("aux"), 0)
        self.last = data.get("last", "")
        self.last_start: int | None = data.get("last_start")


class Humidity:
    """Representation of humidification and dehumidification settings."""

    def __init__(self, data: dict) -> None:
        """Initialize humidification settings."""

        # "humidification":{"target_percent":5,"enabled":"off","mode":"humidifier"}
        # "dehumidification":{"target_percent":40,"enabled":"off","mode":"overcooling"}
        self.target_percent = to_int(data.get("target_percent"), DEFAULT_MIN_HUMIDITY)
        self.enabled = to_bool(data.get("enabled"))
        self.mode = try_parse_enum(
            DehumidificationMode, data.get("mode", DehumidificationMode.UNKNOWN)
        )

    def __repr__(self):
        """Return the representation."""
        return f"Humidity(target_percent={self.target_percent}, enabled={self.enabled}, mode={self.mode})"


class HumidityControl:
    """Representation of humidity control settings."""

    def __init__(self, data: dict) -> None:
        """Initialize humidity control settings."""

        # {'humidification': {'target_percent': 5, 'enabled': 'off', 'mode': 'humidifier'}, 'dehumidification': {'target_percent': 40, 'enabled': 'off', 'mode': 'overcooling'}, 'status': 'none'}
        self.humidification = Humidity(data.get("humidification", {}))
        self.dehumidification = Humidity(data.get("dehumidification", {}))
        self.status = try_parse_enum(
            HumidityControlStatus, data.get("status", HumidityControlStatus.NONE)
        )


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

    current_cool_temp: int
    """Temperature when to start cooling"""
    current_heat_temp: int
    """Temperature when to start heating"""
    display_scale: str
    """Use temperature_unit instead."""

    def __init__(self, data: dict) -> None:
        """Initialize State from data dictionary."""
        self.battery_voltage = to_float(data.get("battery_voltage"), None)
        self.circulating_fan = CirculatingFan(data.get("circulating_fan", {}))
        self.continuous_backlight = to_bool(data.get("continuous_backlight"))
        self.cool_min_temp = to_int(data.get("cool_min_temp"), TEMPERATURE_LOWER_LIMIT)
        self.current_cool_temp = to_int(data.get("current_cool_temp"), None)
        self.current_heat_temp = to_int(data.get("current_heat_temp"), None)

        self.demand_status = DemandStatus(
            data.get("demand_status", {})
        )  # Demand status contains runtime power/demand values for HVAC

        self.display_humidity = to_bool(data.get("display_humidity"))
        self.display_scale = data.get("display_scale", "")
        self.display_temp = to_float(data.get("display_temp"), None)
        self.display_time = to_bool(data.get("display_time"))
        self.fan_mode = try_parse_enum(FanMode, data.get("fan_mode", FanMode.UNKNOWN))
        self.heat_max_temp = to_int(data.get("heat_max_temp"), TEMPERATURE_UPPER_LIMIT)
        self.humidity = to_int(data.get("humidity"), None)
        self.humidity_control = HumidityControl(data.get("humidity_control", {}))
        self.humidity_offset = to_int(data.get("humidity_offset"), 0)
        self.keypad_lockout = to_bool(data.get("keypad_lockout"))
        self.operating_mode = try_parse_enum(
            OperatingMode, data.get("operating_mode", OperatingMode.UNKNOWN)
        )
        self.power_status = data.get("power_status", "")
        self.remote_sensor_status = data.get("remote_sensor_status", "")
        self.status = data.get("status", "")
        self.temp_offset = to_int(data.get("temp_offset"), 0)
        self.wifi_connection_quality = to_int(data.get("wifi_connection_quality"), None)

        # Calculated fields
        self.temperature_unit = (
            UnitOfTemperature.CELSIUS
            if self.display_scale.lower() == "c"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def is_online(self) -> bool | None:
        """Return true if the device is online."""
        return self.status.lower() == "online"

    def __str__(self):
        """Return string representation of State."""
        return (
            f"State(status={self.status}, operating_mode={self.operating_mode}, "
            f"display_temp={self.display_temp}{self.temperature_unit}, "
            f"humidity={self.humidity}%"
        )


class Firmware:
    """Thermostat firmware information."""

    def __init__(self, data: dict) -> None:
        """Initialize FirmwareInfo from data dictionary."""
        self.firmware_version = data.get("firmware_version", "")
        self.bootloader_version = data.get("bootloader_version", "")
        self.wifi_version = data.get("wifi_version", "")


class ThermostatInfo:
    """Thermostat information returned from Sensi websocket."""

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
        self.last_changed_timestamp = to_int(data.get("last_changed_timestamp"), 0)

    def __str__(self):
        """Return string representation of ThermostatInfo."""
        return (
            f"ThermostatInfo(model={self.model_number}, serial={self.serial_number}, "
            f"hw_id={self.unique_hardware_id}, wifi_mac={self.wifi_mac_address}"
        )


class SensiDevice:
    """Representation of a Sensi thermostat."""

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
        self.room_sensor_payload: dict[str, Any] = {}
        self.room_sensor_stats = RoomSensorStats(state.get("sensors"))
        self.room_sensors: list[RoomSensor] = []
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
            self.room_sensor_stats = RoomSensorStats(source.get("sensors"))
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

    def update_room_sensor_summary(self, source: dict[str, Any] | None) -> None:
        """Update room sensor data from the REST summary endpoint."""
        if not source:
            return

        self.room_sensor_payload = source
        self.room_sensor_stats = RoomSensorStats(source)

        sensors: list[RoomSensor] = []

        thermostat_sensor = source.get("thermostat")
        if isinstance(thermostat_sensor, dict):
            sensors.append(
                RoomSensor(
                    thermostat_sensor,
                    default_id="thermostat",
                    default_name="Thermostat",
                    default_type="thermostat",
                )
            )

        source_sensors = source.get("sensors", [])
        if isinstance(source_sensors, list):
            sensors.extend(
                RoomSensor(sensor)
                for sensor in source_sensors
                if isinstance(sensor, dict)
            )

        unique_sensors: list[RoomSensor] = []
        seen_ids: set[str] = set()
        for sensor in sensors:
            key = sensor.identifier or sensor.name
            if not key or key in seen_ids:
                continue

            seen_ids.add(key)
            unique_sensors.append(sensor)

        self.room_sensors = unique_sensors

    def get_room_sensor(self, sensor_id: str) -> RoomSensor | None:
        """Return the current room sensor for a given identifier."""
        return next(
            (
                sensor
                for sensor in self.room_sensors
                if sensor.identifier == sensor_id
            ),
            None,
        )
