"""The Sensi thermostat component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.sensi.auth import SensiConfig, login
from custom_components.sensi.coordinator import SensiUpdateCoordinator

from .const import SENSI_DOMAIN

SUPPORTED_PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Sensi component."""

    hass.data.setdefault(SENSI_DOMAIN, {})
    user_input = entry.data

    config = SensiConfig(
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    try:
        if not await login(hass, config, True):
            raise ConfigEntryAuthFailed
    except Exception as exception:
        raise ConfigEntryNotReady from exception

    coordinator = SensiUpdateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    # entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    hass.data[SENSI_DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "sensi_config": config,
    }
    # hass.config_entries.async_setup_platforms(entry, SUPPORTED_PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True
