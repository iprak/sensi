"""The Sensi thermostat component."""
from __future__ import annotations

from .auth import (
    AuthenticationConfig,
    AuthenticationError,
    login,
)
from .coordinator import SensiDevice, SensiUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONFIG_FAN_SUPPORT,
    DEFAULT_FAN_SUPPORT,
    DOMAIN_DATA_COORDINATOR_KEY,
    LOGGER,
    SENSI_ATTRIBUTION,
    SENSI_DOMAIN,
)

SUPPORTED_PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]


def send_notification(
    hass: HomeAssistant, notification_id: str, title: str, message: str
) -> None:
    """Display a persistent notification."""
    hass.async_create_task(
        hass.services.async_call(
            domain="persistent_notification",
            service="create",
            service_data={
                "title": title,
                "message": message,
                "notification_id": f"{SENSI_DOMAIN}.{notification_id}",
            },
        )
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Sensi component."""

    hass.data.setdefault(SENSI_DOMAIN, {})
    user_input = entry.data

    auth_config = AuthenticationConfig(
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    try:
        await login(hass, auth_config, True)  # Obtain new access_token on startup
    except AuthenticationError as err:
        # Raising ConfigEntryAuthFailed will automatically put the config entry in a
        # failure state and start a reauth flow.
        # https://developers.home-assistant.io/docs/integration_setup_failures/
        raise ConfigEntryAuthFailed from err

    except Exception as err:
        LOGGER.warning("Unable to authenticate", exc_info=True)
        raise ConfigEntryNotReady(
            "Unable to authenticate. Sensi integration is not ready."
        ) from err

    coordinator = SensiUpdateCoordinator(hass, auth_config)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(SENSI_DOMAIN, {})
    hass.data[SENSI_DOMAIN][entry.entry_id] = {
        DOMAIN_DATA_COORDINATOR_KEY: coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, SUPPORTED_PLATFORMS
    ):
        hass.data[SENSI_DOMAIN].pop(entry.entry_id)
    return unload_ok


class SensiEntity(CoordinatorEntity):
    """Representation of a Sensi entity."""

    _attr_has_entity_name = True
    _attr_attribution = SENSI_ATTRIBUTION

    def __init__(self, device: SensiDevice) -> None:
        """Initialize the entity."""

        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = device.identifier

        self._attr_device_info = DeviceInfo(
            identifiers={(SENSI_DOMAIN, device.identifier)},
            name=device.name,
            manufacturer="Sensi",
            model=device.model,
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available.

        The entity is not available if there is no data or if the device is offline.
        """
        return (
            self._device
            and not self._device.offline
            and self.coordinator.data
            and self.coordinator.data.get(self._device.identifier)
        )


class SensiDescriptionEntity(SensiEntity):
    """Representation of a Sensi description entity."""

    def __init__(self, device: SensiDevice, description: EntityDescription) -> None:
        """Initialize the entity."""

        super().__init__(device)
        self.entity_description = description

        # Override the _attr_unique_id to include description.key
        # description would be passed for sensor and switch domains.
        # https://developers.home-assistant.io/docs/entity_registry_index/
        self._attr_unique_id = f"{device.identifier}_{description.key}"


def get_fan_support(device: SensiDevice, entry: ConfigEntry) -> bool:
    """Determine if fan is supported."""

    options = entry.options.get(CONFIG_FAN_SUPPORT, {})
    return options.get(device.identifier, DEFAULT_FAN_SUPPORT)


def set_fan_support(
    hass: HomeAssistant, device: SensiDevice, entry: ConfigEntry, value: bool
) -> None:
    """Update the fan support status in ConfigEntry."""

    new_data = entry.data.copy()
    new_options = entry.options.copy()
    fan_options = new_options.get(CONFIG_FAN_SUPPORT, {})
    fan_options[device.identifier] = value
    new_options[CONFIG_FAN_SUPPORT] = fan_options

    hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)
