"""Config flow for Sensi thermostat."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from custom_components.sensi.auth import (
    AuthenticationConfig,
    AuthenticationError,
    SensiConnectionError,
    login,
)

from .const import SENSI_DOMAIN, SENSI_NAME

_LOGGER = logging.getLogger(__name__)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SensiFlowHandler(config_entries.ConfigFlow, domain=SENSI_DOMAIN):
    """Config flow for Sensi thermostat."""

    VERSION = 1

    def __init__(self):
        """Start a config flow."""
        self._reauth_unique_id = None

    async def _async_validate_input(self, config: AuthenticationConfig):
        """Validate user input."""
        try:
            await login(self.hass, config, True)
        except SensiConnectionError:
            return {"base": "cannot_connect"}
        except AuthenticationError:
            return {"base": "invalid_auth"}
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(str(err))
            return {"base": "unknown"}

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            config = AuthenticationConfig(
                username=user_input[CONF_USERNAME], password=user_input[CONF_PASSWORD]
            )
            errors = await self._async_validate_input(config)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=SENSI_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        # pylint: disable=unused-argument
        """Handle reauthentication."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauthentication."""
        errors = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        username = existing_entry.data[CONF_USERNAME]
        if user_input is not None:
            config = AuthenticationConfig(
                username=username,
                password=user_input[CONF_PASSWORD],
            )
            errors = await self._async_validate_input(config)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={CONF_USERNAME: username},
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )
