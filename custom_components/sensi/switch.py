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

from . import SensiDescriptionEntity, get_fan_support, set_fan_support
from .const import (
    CONFIG_FAN_SUPPORT,
    DOMAIN_DATA_COORDINATOR_KEY,
    SENSI_DOMAIN,
    Capabilities,
    Settings,
)
from .coordinator import SensiDevice, SensiUpdateCoordinator


@dataclass
class SensiCapabilityEntityDescriptionMixin:
    """Mixin for Sensi thermostat setting."""

    capability: Capabilities
    """Capability related to the description"""


@dataclass
class SensiCapabilityEntityDescription(
    SwitchEntityDescription, SensiCapabilityEntityDescriptionMixin
):
    """Representation of a Sensi thermostat setting."""


SWITCH_TYPES: Final = (
    SensiCapabilityEntityDescription(
        key=Settings.DISPLAY_HUMIDITY,
        name="Display Humidity",
        icon="mdi:water-percent",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.DISPLAY_HUMIDITY,
    ),
    SensiCapabilityEntityDescription(
        key=Settings.CONTINUOUS_BACKLIGHT,
        name="Continuous Backlight",
        icon="mdi:wall-sconce-flat",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.CONTINUOUS_BACKLIGHT,
    ),
    SensiCapabilityEntityDescription(
        key=Settings.DISPLAY_TIME,
        name="Display Time",
        icon="mdi:clock",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.DISPLAY_TIME,
    ),
    SensiCapabilityEntityDescription(
        key=Settings.KEYPAD_LOCKOUT,
        name="Keypad lockout",
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
        capability=Capabilities.KEYPAD_LOCKOUT,
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
                entities.append(SensiCapabilitySettingSwitch(device, description))

        entities.append(SensiFanSupportSwitch(device, entry))

    async_add_entities(entities)


class SensiCapabilitySettingSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of a Sensi thermostat capability setting."""

    def __init__(
        self, device: SensiDevice, description: SwitchEntityDescription
    ) -> None:
        """Initialize the setting."""
        super().__init__(device, description)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=device.coordinator.hass,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._device.get_setting(self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._device.async_set_setting(self.entity_description.key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._device.async_set_setting(self.entity_description.key, False)
        self.async_write_ha_state()


class SensiFanSupportSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of Sensi thermostat fan support setting."""

    def __init__(self, device: SensiDevice, entry: ConfigEntry) -> None:
        """Initialize the setting."""

        description = SwitchEntityDescription(
            key=CONFIG_FAN_SUPPORT,
            name="Fan support",
            icon="mdi:fan-off",
            entity_category=EntityCategory.CONFIG,
        )

        super().__init__(device, description)

        # Cache status to avoid querying ConfigEntry
        self._status: bool | None = None

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=device.coordinator.hass,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if self._status is None:
            self._status = get_fan_support(self._device, self._entry)
        return self._status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        set_fan_support(self.hass, self._device, self._entry, True)
        self._status = True
        self.async_write_ha_state()

        # Force coordinator refresh to get climate entity to use new fan status
        await self._device.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        set_fan_support(self.hass, self._device, self._entry, False)
        self._status = False
        self.async_write_ha_state()

        # Force coordinator refresh to get climate entity to use new fan status
        await self._device.coordinator.async_request_refresh()
