"""Sensi thermostat setting switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.sensi import SensiDescriptionEntity
from custom_components.sensi.coordinator import SensiDevice, SensiUpdateCoordinator

from .const import (
    DOMAIN_DATA_COORDINATOR_KEY,
    SENSI_DOMAIN,
    Capabilities,
    DisplayProperties,
)


@dataclass
class SensiSwitchEntityDescriptionMixin:
    """Mixin for Sensi thermostat setting."""

    capability: Capabilities
    """Capability related to the description"""


@dataclass
class SensiSwitchEntityDescription(
    SwitchEntityDescription, SensiSwitchEntityDescriptionMixin
):
    """Representation of a Sensi thermostat setting."""


SWITCH_TYPES: Final = (
    SensiSwitchEntityDescription(
        key=DisplayProperties.DISPLAY_HUMIDITY,
        name="Display Humidity",
        icon="mdi:water-percent",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.DISPLAY_HUMIDITY,
    ),
    SensiSwitchEntityDescription(
        key=DisplayProperties.CONTINUOUS_BACKLIGHT,
        name="Continuous Backlight",
        icon="mdi:wall-sconce-flat",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.CONTINUOUS_BACKLIGHT,
    ),
    SensiSwitchEntityDescription(
        key=DisplayProperties.DISPLAY_TIME,
        name="Display Time",
        icon="mdi:clock",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.DISPLAY_TIME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat setting switches."""
    data = hass.data[SENSI_DOMAIN][entry.entry_id]
    coordinator: SensiUpdateCoordinator = data[DOMAIN_DATA_COORDINATOR_KEY]

    entities = []
    for device in coordinator.get_devices():
        for description in SWITCH_TYPES:
            # A device might not support a setting e.g. Continuous Backlight
            if device.supports(description.capability):
                entities.append(SensiDisplaySettingSwitch(device, description))

    async_add_entities(entities)


class SensiDisplaySettingSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of a Sensi thermostat display setting."""

    def __init__(
        self, device: SensiDevice, description: SwitchEntityDescription
    ) -> None:
        """Initialize the configuration."""
        super().__init__(device, description)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.identifier}_{description.key}",
            hass=device.coordinator.hass,
        )

    @property
    def is_on(self) -> bool | None:
        return self._device.get_display_setting(self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_set_display_setting(self.entity_description.key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_set_display_setting(self.entity_description.key, False)
        self.async_write_ha_state()
