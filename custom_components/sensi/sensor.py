"""Sensi thermostat sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_BATTERY_VOLTAGE, SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiDevice
from .data import RoomSensor
from .entity import SensiDescriptionEntity, SensiEntity


def calculate_battery_level(voltage: float) -> int | None:
    """Calculate the battery level."""
    # https://devzone.nordicsemi.com/f/nordic-q-a/28101/how-to-calculate-battery-voltage-into-percentage-for-aa-2-batteries-without-fluctuations
    # https://forum.arduino.cc/t/calculate-battery-percentage-of-alkaline-batteries-using-the-voltage/669958/17
    if voltage is None:
        return None
    mvolts = voltage * 1000
    # return "low" if (((voltage * 1000) - 900) * 100) / (600) <= 30 else "good"
    if mvolts >= 3000:
        return 100
    if mvolts > 2900:
        return 100 - int(((3000 - mvolts) * 58) / 100)
    if mvolts > 2740:
        return 42 - int(((2900 - mvolts) * 24) / 160)
    if mvolts > 2440:
        return 18 - int(((2740 - mvolts) * 12) / 300)
    if mvolts > 2100:
        return 6 - int(((2440 - mvolts) * 6) / 340)

    return 0


@dataclass(frozen=True)
class SensiSensorEntityDescription(SensorEntityDescription):
    """Representation of a Sensi thermostat sensor."""

    extra_state_attributes_fn: Callable[[Any], dict[str, str]] | None = None
    value_fn: Callable[[SensiDevice], StateType] = None


@dataclass(frozen=True)
class SensiRoomSensorEntityDescription(SensorEntityDescription):
    """Representation of a dynamic room sensor metric."""

    value_fn: Callable[[RoomSensor], StateType] = None


SENSOR_TYPES: Final = [
    SensiSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.display_temp,
    ),
    SensiSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.humidity,
    ),
    SensiSensorEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        extra_state_attributes_fn=lambda device: {
            ATTR_BATTERY_VOLTAGE: device.state.battery_voltage
        },
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: calculate_battery_level(device.state.battery_voltage),
    ),
    SensiSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:thermometer-low",
        key="cool_min_temp",
        name="Min setpoint",
        value_fn=lambda device: device.state.cool_min_temp,
    ),
    SensiSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:thermometer-high",
        key="heat_max_temp",
        name="Max setpoint",
        value_fn=lambda device: device.state.heat_max_temp,
    ),
    SensiSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:fan",
        key="fan_speed",
        name="Fan speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.demand_status.fan,
    ),
    SensiSensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:wifi-strength-outline",
        key="wifi_strength",
        name="Wifi strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorDeviceClass.SIGNAL_STRENGTH,
        value_fn=lambda device: device.state.wifi_connection_quality,
    ),
]

ROOM_SENSOR_TYPES: Final = [
    SensiRoomSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.temperature,
    ),
    SensiRoomSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.humidity,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""
    coordinator = entry.runtime_data
    entities = [
        SensiSensorEntity(hass, device, description, entry)
        for device in coordinator.get_devices()
        for description in SENSOR_TYPES
    ]
    entities.extend(
        SensiRoomSensorEntity(
            hass, device, room_sensor.identifier, description, entry
        )
        for device in coordinator.get_devices()
        for room_sensor in device.room_sensors
        for description in ROOM_SENSOR_TYPES
        if room_sensor.identifier and description.value_fn(room_sensor) is not None
    )

    async_add_entities(entities)


class SensiSensorEntity(SensiDescriptionEntity, SensorEntity):
    """Representation of a Sensi thermostat sensor."""

    entity_description: SensiSensorEntityDescription = None

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        description: SensiSensorEntityDescription,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, description, entry)

        # Note: self.hass is not set at this point
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=hass,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return (
            self.entity_description.value_fn(self._device)
            if self.entity_description.value_fn
            else None
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return (
            self._state.temperature_unit
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        return (
            self.entity_description.extra_state_attributes_fn(self._device)
            if self.entity_description.extra_state_attributes_fn
            else None
        )

    @property
    def icon(self) -> str | None:
        """Return icon for sensor."""
        return self.entity_description.icon


class SensiRoomSensorEntity(SensiEntity, SensorEntity):
    """Representation of a thermostat or remote room sensor."""

    entity_description: SensiRoomSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        sensor_id: str,
        description: SensiRoomSensorEntityDescription,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the room sensor entity."""
        super().__init__(device, entry)
        self.entity_description = description
        self._sensor_id = sensor_id

        room_sensor = self._room_sensor
        sensor_name = room_sensor.name if room_sensor else sensor_id

        self._attr_name = f"{sensor_name} {description.name}"
        self._attr_unique_id = (
            f"{device.identifier}_room_sensor_{sensor_id}_{description.key}"
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{sensor_name}_{description.key}",
            hass=hass,
        )

    @property
    def _room_sensor(self) -> RoomSensor | None:
        """Return the current room sensor model."""
        return self._device.get_room_sensor(self._sensor_id)

    @property
    def available(self) -> bool:
        """Return if the room sensor entity is available."""
        return super().available and self._room_sensor is not None

    @property
    def native_value(self) -> StateType:
        """Return the room sensor value."""
        room_sensor = self._room_sensor
        if not room_sensor:
            return None

        return self.entity_description.value_fn(room_sensor)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the room sensor."""
        return (
            self._state.temperature_unit
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra room sensor details."""
        room_sensor = self._room_sensor
        return room_sensor.as_attributes() if room_sensor else None
