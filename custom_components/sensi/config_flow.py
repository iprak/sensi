"""Config flow for Sensi thermostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .auth import (
    AuthenticationConfig,
    AuthenticationError,
    SensiConnectionError,
    refresh_access_token,
)
from .const import CONFIG_REFRESH_TOKEN, LOGGER, SENSI_DOMAIN, SENSI_NAME

# REAUTH_SCHEMA = vol.Schema({vol.Required(CONFIG_REFRESH_TOKEN): str})

AUTH_DATA_SCHEMA = vol.Schema(
    {
        # vol.Required(CONF_USERNAME): str,
        # vol.Required(CONF_PASSWORD): str,
        vol.Required(CONFIG_REFRESH_TOKEN): str,
    }
)


class SensiFlowHandler(config_entries.ConfigFlow, domain=SENSI_DOMAIN):
    """Config flow for Sensi thermostat."""

    VERSION = 1

    def __init__(self) -> None:
        """Start a config flow."""
        self._reauth_unique_id = None

    async def _try_login(self, config: AuthenticationConfig):
        """Try login with supplied credentials."""
        try:
            await refresh_access_token(self.hass, config.refresh_token)
        except SensiConnectionError:
            return {"base": "cannot_connect"}
        except AuthenticationError:
            return {"base": "invalid_auth"}
        except Exception as err:  # pylint: disable=broad-except # noqa: BLE001
            LOGGER.exception(str(err))
            return {"base": "unknown"}

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            config = AuthenticationConfig(
                # username=user_input[CONF_USERNAME],
                # password=user_input[CONF_PASSWORD],
                refresh_token=user_input[CONFIG_REFRESH_TOKEN],
            )
            errors = await self._try_login(config)
            if not errors:
                await self.async_set_unique_id(
                    config.user_id
                )  # Use user_id as unique_id
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
        # username = existing_entry.data[CONF_USERNAME]
        if user_input is not None:
            config = AuthenticationConfig(
                # username=username,
                # password=user_input[CONF_PASSWORD],
                refresh_token=user_input[CONFIG_REFRESH_TOKEN],
            )
            errors = await self._try_login(config)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        # CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONFIG_REFRESH_TOKEN: user_input[CONFIG_REFRESH_TOKEN],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # The input for user and re_config is the same
        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_DATA_SCHEMA,
            errors=errors,
        )
