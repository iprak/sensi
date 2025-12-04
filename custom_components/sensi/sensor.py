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

from . import SensiConfigEntry, SensiDescriptionEntity
from .const import ATTR_BATTERY_VOLTAGE, SENSI_DOMAIN, Settings
from .coordinator import SensiDevice


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


SENSOR_TYPES: Final = (
    SensiSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.temperature,
    ),
    SensiSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.humidity,
    ),
    SensiSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        extra_state_attributes_fn=lambda device: {
            ATTR_BATTERY_VOLTAGE: device.battery_voltage
        },
        value_fn=lambda device: calculate_battery_level(device.battery_voltage),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensiSensorEntityDescription(
        key=Settings.COOL_MIN_TEMP,
        name="Min setpoint",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.min_temp,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensiSensorEntityDescription(
        key=Settings.HEAT_MAX_TEMP,
        name="Max setpoint",
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.max_temp,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensiSensorEntityDescription(
        key="fan_speed",
        name="Fan speed",
        value_fn=lambda device: device.fan_speed,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        icon="mdi:fan",
    ),
    SensiSensorEntityDescription(
        key="wifi_strength",
        name="Wifi strength",
        value_fn=lambda device: device.wifi_strength,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        icon="mdi:wifi-strength-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""
    coordinator = entry.runtime_data
    entities = [
        SensiSensorEntity(device, description)
        for device in coordinator.get_devices()
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class SensiSensorEntity(SensiDescriptionEntity, SensorEntity):
    """Representation of a Sensi thermostat sensor."""

    entity_description: SensiSensorEntityDescription = None

    def __init__(
        self,
        device: SensiDevice,
        description: SensiSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, description)

        # Note: self.hass is not set at this point
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=device.coordinator.hass,
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
            self._device.temperature_unit
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
