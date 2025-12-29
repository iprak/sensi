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

from . import get_config_option, set_config_option
from .const import (
    CONFIG_AUX_HEATING,
    CONFIG_FAN_SUPPORT,
    DEFAULT_CONFIG_FAN_SUPPORT,
    SENSI_DOMAIN,
)
from .coordinator import SensiConfigEntry, SensiDevice, SensiUpdateCoordinator
from .data import OperatingMode
from .entity import SensiDescriptionEntity
from .event import SettingEventName
from .utils import raise_if_error


@dataclass
class SensiCapabilityEntityDescriptionMixin:
    """Mixin for Sensi thermostat setting."""

    setting: SettingEventName


@dataclass
class SensiCapabilityEntityDescription(
    SwitchEntityDescription, SensiCapabilityEntityDescriptionMixin
):
    """Representation of a Sensi thermostat setting."""

    entity_category = EntityCategory.CONFIG


SWITCH_TYPES: Final = [
    # The `key` represents the attribute on State and Capabilities
    SensiCapabilityEntityDescription(
        key="display_humidity",
        setting=SettingEventName.DISPLAY_HUMIDITY,
        name="Display Humidity",
        icon="mdi:water-percent",
    ),
    SensiCapabilityEntityDescription(
        key="continuous_backlight",
        setting=SettingEventName.CONTINUOUS_BACKLIGHT,
        name="Continuous Backlight",
        icon="mdi:wall-sconce-flat",
    ),
    SensiCapabilityEntityDescription(
        key="display_time",
        setting=SettingEventName.DISPLAY_TIME,
        name="Display Time",
        icon="mdi:clock",
    ),
    SensiCapabilityEntityDescription(
        key="keypad_lockout",
        setting=SettingEventName.KEYPAD_LOCKOUT,
        name="Keypad lockout",
        icon="mdi:lock",
    ),
]


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
            if getattr(capabilities, description.key)
        )

        entities.append(SensiFanSupportSwitch(device, entry, coordinator))
        entities.append(SensiAuxHeatSwitch(device, coordinator))

    async_add_entities(entities)


class SensiCapabilitySettingSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of a Sensi thermostat capability setting."""

    entity_description: SensiCapabilityEntityDescription

    def __init__(
        self,
        device: SensiDevice,
        description: SensiCapabilityEntityDescription,
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
        return getattr(self._device.state, self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        await self._set_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        (error, _) = await self.coordinator.client.async_set_bool_setting(
            self._device, self.entity_description.setting, value
        )
        raise_if_error(error, self.entity_description.name, value)
        self.async_write_ha_state()
        # The setting should not change thermostat operation, so let update happen on regular schedule


class SensiFanSupportSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of Sensi thermostat fan support setting."""

    def __init__(
        self,
        device: SensiDevice,
        entry: SensiConfigEntry,
        coordinator: SensiUpdateCoordinator,
    ) -> None:
        """Initialize the setting."""

        description = SwitchEntityDescription(
            key=CONFIG_FAN_SUPPORT,
            name="Fan",
            icon="mdi:fan-off",
            entity_category=EntityCategory.CONFIG,
        )

        super().__init__(device, description, coordinator)

        # Cache status to avoid querying ConfigEntry
        self._status: bool | None = None

        self._entry = entry
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=coordinator.hass,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if self._status is None:
            self._status = get_config_option(
                self._device,
                self._entry,
                CONFIG_FAN_SUPPORT,
                DEFAULT_CONFIG_FAN_SUPPORT,
            )
        return self._status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._set_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        set_config_option(
            self.hass, self._device, self._entry, CONFIG_FAN_SUPPORT, value
        )
        self._status = value
        self.async_write_ha_state()

        # Force coordinator refresh to get climate entity to use new fan status
        await self.coordinator.async_request_refresh()


class SensiAuxHeatSwitch(SensiDescriptionEntity, SwitchEntity):
    """Representation of Sensi thermostat aux heating setting."""

    _last_hvac_mode_before_aux_heat: HVACMode | str | None

    def __init__(
        self,
        device: SensiDevice,
        coordinator: SensiUpdateCoordinator,
    ) -> None:
        """Initialize the setting."""

        description = SwitchEntityDescription(
            key=CONFIG_AUX_HEATING,
            name="Auxiliary Heating",
            icon="mdi:heat-pump",
            entity_category=EntityCategory.CONFIG,
        )

        super().__init__(device, description, coordinator)

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{SENSI_DOMAIN}_{device.name}_{description.key}",
            hass=coordinator.hass,
        )

        self._last_operating_mode_before_aux_heat = device.state.operating_mode

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.capabilities.operating_mode_settings.aux

    @property
    def is_on(self) -> bool | None:
        """Return True if aux heating is on."""
        return self._device.state.operating_mode == OperatingMode.AUX

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn aux heating on."""

        self._last_operating_mode_before_aux_heat = self._device.state.operating_mode

        (error, _) = await self.coordinator.client.async_set_operating_mode(
            self._device, OperatingMode.AUX
        )
        raise_if_error(error, "operating mode", OperatingMode.AUX.value)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn aux heating off."""

        (error, _) = await self.coordinator.client.async_set_operating_mode(
            self._device, self._last_operating_mode_before_aux_heat
        )
        raise_if_error(
            error, "operating mode", self._last_operating_mode_before_aux_heat.value
        )
        self.async_write_ha_state()
