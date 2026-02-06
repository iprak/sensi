"""Base Sensi entity."""

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SENSI_ATTRIBUTION, SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiUpdateCoordinator
from .data import SensiDevice, State


class SensiEntity(CoordinatorEntity[SensiUpdateCoordinator]):
    """Representation of a Sensi entity."""

    _attr_has_entity_name = True
    _attr_attribution = SENSI_ATTRIBUTION

    def __init__(
        self,
        device: SensiDevice,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry.runtime_data)
        self._device = device
        self._entry = entry
        self._attr_unique_id = device.identifier

        self._attr_device_info = DeviceInfo(
            identifiers={(SENSI_DOMAIN, device.identifier)},
            name=device.name,
            manufacturer="Sensi",
            model=device.info.model_number,
            serial_number=device.info.serial_number,
        )

    @property
    def _state(self) -> State:
        """Current device state."""
        return self._device.state

    @property
    def available(self) -> bool:
        """Return if the entity is available.

        The entity is not available if the fetch failed or if the device is offline.
        """
        return super().available and self._state.is_online


class SensiDescriptionEntity(SensiEntity):
    """Representation of a Sensi description entity."""

    def __init__(
        self,
        device: SensiDevice,
        description: EntityDescription,
        entry: SensiConfigEntry,
    ) -> None:
        """Initialize the entity."""

        super().__init__(device, entry)
        self.entity_description = description

        # Override the _attr_unique_id to include description.key
        # description would be passed for sensor and switch domains.
        # https://developers.home-assistant.io/docs/entity_registry_index/
        self._attr_unique_id = f"{device.identifier}_{description.key}"
