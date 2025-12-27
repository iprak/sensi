"""Sensi thermostat setting switches."""

from __future__ import annotations

from collections.abc import Callable
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

from . import get_fan_support, set_fan_support
from .const import CONFIG_AUX_HEATING, CONFIG_FAN_SUPPORT, SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiUpdateCoordinator
from .data import Capabilities, OperatingMode, SensiDevice
from .entity import SensiDescriptionEntity
from .event import SettingEventName


@dataclass
class SensiCapabilityEntityDescriptionMixin:
    """Mixin for Sensi thermostat setting."""

    supports_fn: Callable[[Capabilities], bool]
    value_fn: Callable[[SensiDevice], bool]


@dataclass
class SensiCapabilityEntityDescription(
    SwitchEntityDescription, SensiCapabilityEntityDescriptionMixin
):
    """Representation of a Sensi thermostat setting."""

    entity_category = EntityCategory.CONFIG


SWITCH_TYPES: Final = (
    SensiCapabilityEntityDescription(
        key=SettingEventName.DISPLAY_HUMIDITY,
        name="Display Humidity",
        icon="mdi:water-percent",
        supports_fn=lambda src: src.display_humidity,
        value_fn=lambda device: device.state.display_humidity,
    ),
    SensiCapabilityEntityDescription(
        key=SettingEventName.CONTINUOUS_BACKLIGHT,
        name="Continuous Backlight",
        icon="mdi:wall-sconce-flat",
        supports_fn=lambda src: src.continuous_backlight,
        value_fn=lambda device: device.state.continuous_backlight,
    ),
    SensiCapabilityEntityDescription(
        key=SettingEventName.DISPLAY_TIME,
        name="Display Time",
        icon="mdi:clock",
        supports_fn=lambda src: src.display_time,
        value_fn=lambda device: device.state.display_time,
    ),
    SensiCapabilityEntityDescription(
        key=SettingEventName.KEYPAD_LOCKOUT,
        name="Keypad lockout",
        icon="mdi:lock",
        supports_fn=lambda src: src.keypad_lockout,
        value_fn=lambda device: device.state.keypad_lockout,
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
        capabilities = device.capabilities
        # A device might not support a setting e.g. Continuous Backlight
        entities.extend(
            SensiCapabilitySettingSwitch(device, description, coordinator)
            for description in SWITCH_TYPES
            if description.supports_fn(capabilities)
        )

        # entities.append(SensiFanSupportSwitch(device, entry))
        # entities.append(SensiAuxHeatSwitch(device, entry))

    async_add_entities(entities)


class SensiCapabilitySettingSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of a Sensi thermostat capability setting."""

    def __init__(
        self,
        device: SensiDevice,
        description: SwitchEntityDescription,
        coordinator: SensiUpdateCoordinator,
    ) -> None:
        """Initialize the setting."""
        super().__init__(device, description, coordinator)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",  # Use same key as before
            hass=coordinator.hass,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.value_fn(self._device)

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
        return self._device.capabilities.operating_mode_settings.aux
        # (Capabilities.OPERATING_MODE_AUX)

    @property
    def is_on(self) -> bool | None:
        """Return True if aux heating is on."""
        return self._device.state.operating_mode == OperatingMode.AUX

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
