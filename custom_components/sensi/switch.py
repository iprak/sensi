"""Sensi thermostat setting switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.climate import HVACMode
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SensiConfigEntry, SensiDescriptionEntity, get_fan_support, set_fan_support
from .const import (
    CONFIG_AUX_HEATING,
    CONFIG_FAN_SUPPORT,
    SENSI_DOMAIN,
    Capabilities,
    OperatingModes,
    Settings,
)
from .coordinator import SensiDevice


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
    entry: SensiConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Sensi thermostat setting switches."""
    coordinator = entry.runtime_data

    entities = []
    for device in coordinator.get_devices():
        # A device might not support a setting e.g. Continuous Backlight
        entities.extend(
            SensiCapabilitySettingSwitch(device, description)
            for description in SWITCH_TYPES
            if device.supports(description.capability)
        )

        entities.append(SensiFanSupportSwitch(device, entry))
        entities.append(SensiAuxHeatSwitch(device, entry))

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
        if await self._device.async_set_setting(self.entity_description.key, True):
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if await self._device.async_set_setting(self.entity_description.key, False):
            self.async_write_ha_state()


class SensiFanSupportSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of Sensi thermostat fan support setting."""

    def __init__(self, device: SensiDevice, entry: SensiConfigEntry) -> None:
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


class SensiAuxHeatSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of Sensi thermostat aux heating setting."""

    _last_hvac_mode_before_aux_heat: HVACMode | str | None

    def __init__(self, device: SensiDevice, entry: SensiConfigEntry) -> None:
        """Initialize the setting."""

        description = SwitchEntityDescription(
            key=CONFIG_AUX_HEATING,
            name="Aux Heating",
            icon="mdi:heat-pump",
            entity_category=EntityCategory.CONFIG,
        )

        super().__init__(device, description)

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=device.coordinator.hass,
        )

        self._last_hvac_mode_before_aux_heat = device.hvac_mode

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.supports(Capabilities.OPERATING_MODE_AUX)

    @property
    def is_on(self) -> bool | None:
        """Return True if aux heating is on."""
        return self._device.operating_mode == OperatingModes.AUX

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn aux heating on."""
        if self._device.offline:
            return

        self._last_hvac_mode_before_aux_heat = self._device.hvac_mode

        if await self._device.async_enable_aux_mode():
            self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn aux heating off."""
        if await self._device.async_set_hvac_mode(self._last_hvac_mode_before_aux_heat):
            self.async_schedule_update_ha_state(True)
