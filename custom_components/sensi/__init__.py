"""The Sensi device component."""

from __future__ import annotations

from copy import deepcopy

import aiohttp

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import StateType
from homeassistant.util.ssl import get_default_context

from .auth import AuthenticationError, SensiConnectionError, get_stored_config
from .client import SensiClient
from .const import LOGGER, SENSI_DOMAIN
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


async def async_unload_entry(hass: HomeAssistant, entry: SensiConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data
    if coordinator:
        await coordinator.client.stop()
    return await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)


def get_config_option(
    device: SensiDevice, entry: SensiConfigEntry, key: str, default: StateType
) -> StateType:
    """Get the value of a config option."""

    options = entry.options.get(key, {})
    return options.get(device.identifier, default)


def set_config_option(
    hass: HomeAssistant,
    device: SensiDevice,
    entry: SensiConfigEntry,
    key: str,
    value: StateType,
) -> None:
    """Set the value of a config option."""

    new_options = deepcopy({**entry.options})
    options = new_options.get(key, {})
    options[device.identifier] = value
    new_options[key] = options

    hass.config_entries.async_update_entry(entry, options=new_options)
