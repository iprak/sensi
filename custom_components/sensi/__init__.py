"""The Sensi device component."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.util.ssl import get_default_context

from .auth import AuthenticationError, SensiConnectionError, get_stored_config
from .client import SensiClient
from .const import CONFIG_FAN_SUPPORT, DEFAULT_FAN_SUPPORT, LOGGER, SENSI_DOMAIN
from .coordinator import SensiConfigEntry, SensiUpdateCoordinator
from .data import SensiDevice

SUPPORTED_PLATFORMS = [
    Platform.BINARY_SENSOR,
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


async def async_setup_entry(hass: HomeAssistant, entry: SensiConfigEntry):
    """Set up the Sensi component."""

    hass.data.setdefault(SENSI_DOMAIN, {})

    try:
        config = await get_stored_config(hass)
        connector = aiohttp.TCPConnector(force_close=True, ssl=get_default_context())
        client = SensiClient(hass, config, connector)
        await client.wait_for_devices()

        entry.runtime_data = SensiUpdateCoordinator(hass, config, client)
        await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)
    except ConfigEntryAuthFailed:
        # Pass ConfigEntryAuthFailed, this can be raised from the coordinator
        raise
    except (AuthenticationError, SensiConnectionError, TimeoutError) as err:
        # Raising ConfigEntryAuthFailed will automatically put the config entry in a
        # failure state and start a reauth flow.
        # https://developers.home-assistant.io/docs/integration_setup_failures/
        raise ConfigEntryAuthFailed from err

    except Exception as err:
        LOGGER.warning("Unable to authenticate", exc_info=True)
        raise ConfigEntryNotReady(
            "Unable to authenticate. Sensi integration is not ready."
        ) from err

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)


def get_fan_support(device: SensiDevice, entry: SensiConfigEntry) -> bool:
    """Determine if fan is supported."""

    options = entry.options.get(CONFIG_FAN_SUPPORT, {})
    return options.get(device.identifier, DEFAULT_FAN_SUPPORT)


def set_fan_support(
    hass: HomeAssistant, device: SensiDevice, entry: SensiConfigEntry, value: bool
) -> None:
    """Update the fan support status in ConfigEntry."""

    new_data = entry.data.copy()
    new_options = entry.options.copy()
    fan_options = new_options.get(CONFIG_FAN_SUPPORT, {})
    fan_options[device.identifier] = value
    new_options[CONFIG_FAN_SUPPORT] = fan_options

    hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)
