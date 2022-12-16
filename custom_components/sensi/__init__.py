"""The Sensi thermostat component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.sensi.auth import AuthenticationConfig, login
from custom_components.sensi.coordinator import SensiUpdateCoordinator

from .const import DOMAIN_DATA_COORDINATOR_KEY, SENSI_DOMAIN

SUPPORTED_PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Sensi component."""

    hass.data.setdefault(SENSI_DOMAIN, {})
    user_input = entry.data

    auth_config = AuthenticationConfig(
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    try:
        if not await login(hass, auth_config, True):
            raise ConfigEntryAuthFailed
    except Exception as exception:
        raise ConfigEntryNotReady from exception

    coordinator = SensiUpdateCoordinator(hass, auth_config)
    await coordinator.async_config_entry_first_refresh()

    hass.data[SENSI_DOMAIN][entry.entry_id] = {
        DOMAIN_DATA_COORDINATOR_KEY: coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True
