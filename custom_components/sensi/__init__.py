"""The Sensi thermostat component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.sensi.auth import (
    AuthenticationConfig,
    AuthenticationError,
    login,
)
from custom_components.sensi.coordinator import SensiUpdateCoordinator

from .const import DOMAIN_DATA_COORDINATOR_KEY, SENSI_DOMAIN

SUPPORTED_PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


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
        _LOGGER.warning("Unable to authenticate", exc_info=True)
        raise ConfigEntryNotReady(
            "Unable to authenticate. Sensi integration is not ready."
        ) from err

    coordinator = SensiUpdateCoordinator(hass, auth_config)
    await coordinator.async_config_entry_first_refresh()

    hass.data[SENSI_DOMAIN][entry.entry_id] = {
        DOMAIN_DATA_COORDINATOR_KEY: coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # pylint: disable=unused-argument
    """Unload a config entry."""
    hass.data.pop(SENSI_DOMAIN)
