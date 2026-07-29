"""Sensi thermostat binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiDevice
from .entity import SensiDescriptionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""

    coordinator = entry.runtime_data
    online = BinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    energy_savings = BinarySensorEntityDescription(
        key="energy_savings",
        name="Energy Savings",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    upcoming = BinarySensorEntityDescription(
        key="upcoming_energy_savings",
        name="Upcoming Energy Savings",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    entities = []
    for device in coordinator.get_devices():
        entities.extend(
            [
                OnlineBinarySensorEntity(hass, device, online, entry),
                EnergySavingsEventEntity(hass, device, energy_savings, entry),
                UpcomingEnergySavingsEventEntity(hass, device, upcoming, entry),
            ]
        )

    async_add_entities(entities)


class OnlineBinarySensorEntity(SensiDescriptionEntity, BinarySensorEntity):
    """Representation of a Sensi online status sensor."""

    entity_description: BinarySensorEntityDescription = None

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        description: BinarySensorEntityDescription,
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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state.is_online

    @property
    def available(self) -> bool:
        """Return if the data is available."""

        # The super class checks device online status so we directly return coordinator status
        return self.coordinator.last_update_success


class BaseEnergySavingsEventEntity(SensiDescriptionEntity, BinarySensorEntity):
    """Representation of an energy savings event status sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: SensiDevice,
        description: BinarySensorEntityDescription,
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


class EnergySavingsEventEntity(BaseEnergySavingsEventEntity):
    """Representation of an energy savings event status sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if tenergy savings event is active."""
        demand_response = self._state.demand_response

        if demand_response:
            current_instant = dt_util.naive_now().timestamp()
            start_time = demand_response.start_time
            end_time = demand_response.end_time

            self._attr_extra_state_attributes = {
                "start_time": start_time,
                "end_time": end_time,
            }

            return (
                start_time
                and end_time
                and (start_time.timestamp() <= current_instant)
                and (end_time.timestamp() >= current_instant)
            )

        return False


class UpcomingEnergySavingsEventEntity(BaseEnergySavingsEventEntity):
    """Representation of an energy savings event status sensor."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update binary sensor attributes."""

        demand_response = self._state.demand_response
        self._attr_is_on = False

        if demand_response:
            start_time = demand_response.start_time
            end_time = demand_response.end_time

            if start_time:
                current_instant = dt_util.naive_now().timestamp()
                self._attr_is_on = start_time.timestamp() > current_instant

            self._attr_extra_state_attributes = {
                "start_time": start_time,
                "end_time": end_time,
            }
