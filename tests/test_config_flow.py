"""Tests for Sensi config flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.sensi.auth import (
    AuthenticationConfig,
    AuthenticationError,
    SensiConnectionError,
)
from custom_components.sensi.config_flow import (
    AUTH_DATA_SCHEMA,
    LoginResponse,
    SensiFlowHandler,
)
from custom_components.sensi.const import CONFIG_REFRESH_TOKEN, SENSI_DOMAIN, SENSI_NAME
from homeassistant.core import HomeAssistant


class TestLoginResponse:
    """Test cases for LoginResponse dataclass."""

    def test_login_response_success(self):
        """Test LoginResponse with successful login."""
        config = AuthenticationConfig(
            refresh_token="test_token",
            access_token="access_token",
            expires_at=12345,
            user_id="user123",
        )
        response = LoginResponse(errors=None, config=config)

        assert response.errors is None
        assert response.config == config

    def test_login_response_error(self):
        """Test LoginResponse with error."""
        response = LoginResponse(
            errors={"base": "invalid_auth"},
            config=None,
        )

        assert response.errors == {"base": "invalid_auth"}
        assert response.config is None

    def test_login_response_multiple_errors(self):
        """Test LoginResponse with multiple errors."""
        response = LoginResponse(
            errors={"base": "invalid_auth", "refresh_token": "Required"},
            config=None,
        )

        assert "base" in response.errors
        assert "refresh_token" in response.errors


class TestAuthDataSchema:
    """Test cases for AUTH_DATA_SCHEMA."""

    def test_auth_schema_valid_input(self):
        """Test AUTH_DATA_SCHEMA with valid input."""
        valid_data = {CONFIG_REFRESH_TOKEN: "test_token"}
        result = AUTH_DATA_SCHEMA(valid_data)

        assert result == valid_data

    def test_auth_schema_missing_refresh_token(self):
        """Test AUTH_DATA_SCHEMA with missing refresh token."""
        with pytest.raises(vol.MultipleInvalid):
            AUTH_DATA_SCHEMA({})

    def test_auth_schema_extra_fields_ignored(self):
        """Test AUTH_DATA_SCHEMA rejects extra fields."""
        data = {
            CONFIG_REFRESH_TOKEN: "test_token",
            "extra_field": "extra_value",
        }
        # Schema should reject extra fields by default
        with pytest.raises(vol.MultipleInvalid):
            AUTH_DATA_SCHEMA(data)


class TestSensiFlowHandler:
    """Test cases for SensiFlowHandler config flow."""

    def test_flow_handler_version(self):
        """Test SensiFlowHandler has correct version."""
        assert SensiFlowHandler.VERSION == 1

    @pytest.mark.asyncio
    async def test_try_login_success(self, hass: HomeAssistant):
        """Test _try_login with successful authentication."""
        handler = SensiFlowHandler()
        handler.hass = hass

        config = AuthenticationConfig(refresh_token="test_token")
        new_config = AuthenticationConfig(
            refresh_token="test_token",
            access_token="new_access_token",
            expires_at=12345,
            user_id="user123",
        )

        with patch(
            "custom_components.sensi.config_flow.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.return_value = new_config
            result = await handler._try_login(config)

        assert result.errors is None
        assert result.config == new_config

    @pytest.mark.asyncio
    async def test_try_login_connection_error(self, hass: HomeAssistant):
        """Test _try_login with connection error."""
        handler = SensiFlowHandler()
        handler.hass = hass

        config = AuthenticationConfig(refresh_token="test_token")

        with patch(
            "custom_components.sensi.config_flow.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.side_effect = SensiConnectionError("Connection failed")
            result = await handler._try_login(config)

        assert result.errors == {"base": "cannot_connect"}
        assert result.config is None

    @pytest.mark.asyncio
    async def test_try_login_authentication_error(self, hass: HomeAssistant):
        """Test _try_login with authentication error."""
        handler = SensiFlowHandler()
        handler.hass = hass

        config = AuthenticationConfig(refresh_token="invalid_token")

        with patch(
            "custom_components.sensi.config_flow.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.side_effect = AuthenticationError("Invalid credentials")
            result = await handler._try_login(config)

        assert result.errors == {"base": "invalid_auth"}
        assert result.config is None

    @pytest.mark.asyncio
    async def test_try_login_generic_exception(self, hass: HomeAssistant):
        """Test _try_login with generic exception."""
        handler = SensiFlowHandler()
        handler.hass = hass

        config = AuthenticationConfig(refresh_token="test_token")

        with patch(
            "custom_components.sensi.config_flow.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.side_effect = ValueError("Unexpected error")
            result = await handler._try_login(config)

        assert result.errors == {"base": "unknown"}
        assert result.config is None

    @pytest.mark.asyncio
    async def test_async_step_user_no_input(self, hass: HomeAssistant):
        """Test async_step_user with no user input."""
        handler = SensiFlowHandler()
        handler.hass = hass

        result = await handler.async_step_user(None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["data_schema"] == AUTH_DATA_SCHEMA

    @pytest.mark.asyncio
    async def test_async_step_user_successful_login(self, hass: HomeAssistant):
        """Test async_step_user with successful login."""
        handler = SensiFlowHandler()
        handler.hass = hass

        user_input = {CONFIG_REFRESH_TOKEN: "test_token"}
        new_config = AuthenticationConfig(
            refresh_token="test_token",
            access_token="access_token",
            expires_at=12345,
            user_id="user123",
        )

        with (
            patch.object(handler, "_try_login") as mock_login,
            patch.object(handler, "async_set_unique_id") as mock_unique_id,
            patch.object(handler, "_abort_if_unique_id_configured") as mock_abort,
            patch.object(handler, "async_create_entry") as mock_create,
        ):
            mock_login.return_value = LoginResponse(errors=None, config=new_config)
            mock_unique_id.return_value = None
            mock_abort.return_value = None
            mock_create.return_value = {"type": "create_entry"}

            await handler.async_step_user(user_input)

            mock_login.assert_called_once()
            mock_unique_id.assert_called_once_with("user123")
            mock_abort.assert_called_once()
            mock_create.assert_called_once_with(title=SENSI_NAME, data=user_input)

    @pytest.mark.asyncio
    async def test_async_step_user_login_failure(self, hass: HomeAssistant):
        """Test async_step_user with login failure."""
        handler = SensiFlowHandler()
        handler.hass = hass

        user_input = {CONFIG_REFRESH_TOKEN: "invalid_token"}

        with (
            patch.object(handler, "_try_login") as mock_login,
            patch.object(handler, "async_show_form") as mock_form,
        ):
            mock_login.return_value = LoginResponse(
                errors={"base": "invalid_auth"}, config=None
            )
            mock_form.return_value = {
                "type": "form",
                "errors": {"base": "invalid_auth"},
            }

            await handler.async_step_user(user_input)

            mock_login.assert_called_once()
            mock_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_reauth(self, hass: HomeAssistant):
        """Test async_step_reauth."""
        handler = SensiFlowHandler()
        handler.hass = hass
        handler.context = {"unique_id": "user123"}

        with patch.object(handler, "async_step_reauth_confirm") as mock_reauth_confirm:
            mock_reauth_confirm.return_value = {"type": "form", "step_id": "user"}

            await handler.async_step_reauth({"refresh_token": "token"})

            assert handler._reauth_unique_id == "user123"
            mock_reauth_confirm.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_reauth_confirm_no_input(self, hass: HomeAssistant):
        """Test async_step_reauth_confirm with no user input."""
        handler = SensiFlowHandler()
        handler.hass = hass

        handler.context = {"unique_id": "user123"}

        with patch.object(handler, "async_step_reauth_confirm"):
            await handler.async_step_reauth({})

        mock_entry = MockConfigEntry(
            domain=SENSI_DOMAIN,
            data={CONFIG_REFRESH_TOKEN: "old_token"},
            entry_id="test_entry",
            unique_id="user123",
        )

        with (
            patch.object(handler, "async_set_unique_id") as mock_unique_id,
            patch.object(handler, "async_show_form") as mock_form,
        ):
            mock_unique_id.return_value = mock_entry
            mock_form.return_value = {"type": "form", "step_id": "user"}

            await handler.async_step_reauth_confirm(None)

            mock_unique_id.assert_called_once_with("user123")
            mock_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_reauth_confirm_successful(self, hass: HomeAssistant):
        """Test async_step_reauth_confirm with successful reauthentication."""
        handler = SensiFlowHandler()
        handler.hass = hass

        handler.context = {"unique_id": "user123"}

        with patch.object(handler, "async_step_reauth_confirm"):
            await handler.async_step_reauth({})

        user_input = {CONFIG_REFRESH_TOKEN: "new_token"}
        new_config = AuthenticationConfig(
            refresh_token="new_token",
            access_token="new_access_token",
            expires_at=12345,
            user_id="user123",
        )

        mock_entry = MockConfigEntry(
            domain=SENSI_DOMAIN,
            data={CONFIG_REFRESH_TOKEN: "old_token"},
            entry_id="test_entry",
            unique_id="user123",
        )

        with (
            patch.object(handler, "async_set_unique_id") as mock_unique_id,
            patch.object(handler, "_try_login") as mock_login,
            patch.object(handler, "async_abort") as mock_abort,
        ):
            mock_unique_id.return_value = mock_entry
            mock_login.return_value = LoginResponse(errors=None, config=new_config)
            mock_abort.return_value = {"type": "abort", "reason": "reauth_successful"}

            # Mock the config_entries update and reload
            hass.config_entries.async_update_entry = Mock()
            hass.config_entries.async_reload = AsyncMock()

            await handler.async_step_reauth_confirm(user_input)

            mock_login.assert_called_once()
            hass.config_entries.async_update_entry.assert_called_once()
            hass.config_entries.async_reload.assert_called_once()
            mock_abort.assert_called_once_with(reason="reauth_successful")

    @pytest.mark.asyncio
    async def test_async_step_reauth_confirm_login_failure(self, hass: HomeAssistant):
        """Test async_step_reauth_confirm with login failure."""
        handler = SensiFlowHandler()
        handler.hass = hass
        handler.context = {"unique_id": "user123"}

        with patch.object(handler, "async_step_reauth_confirm"):
            await handler.async_step_reauth({})

        user_input = {CONFIG_REFRESH_TOKEN: "invalid_token"}

        mock_entry = MockConfigEntry(
            domain=SENSI_DOMAIN,
            data={CONFIG_REFRESH_TOKEN: "old_token"},
            entry_id="test_entry",
            unique_id="user123",
        )

        with (
            patch.object(handler, "async_set_unique_id") as mock_unique_id,
            patch.object(handler, "_try_login") as mock_login,
            patch.object(handler, "async_show_form") as mock_form,
        ):
            mock_unique_id.return_value = mock_entry
            mock_login.return_value = LoginResponse(
                errors={"base": "invalid_auth"}, config=None
            )
            mock_form.return_value = {"type": "form", "step_id": "user"}

            await handler.async_step_reauth_confirm(user_input)

            mock_login.assert_called_once()
            mock_form.assert_called_once()
