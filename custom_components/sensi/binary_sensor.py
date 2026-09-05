"""Sensi thermostat binary sensors."""

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_CONSECUTIVE_CONNECTION_FAILURES, SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiDevice
from .entity import SensiDescriptionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat sensors."""

    coordinator = entry.runtime_data
    online_description = BinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    entities = [
        OnlineBinarySensorEntity(hass, device, online_description, entry)
        for device in coordinator.get_devices()
    ]

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

        # The super class checks device online status so we check update failures on the coordinator
        return (
            self.coordinator.consecutive_connection_failures
            <= MAX_CONSECUTIVE_CONNECTION_FAILURES
        )
