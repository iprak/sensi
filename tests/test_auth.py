"""Tests for Sensi authentication module."""

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.sensi.auth import (
    KEY_ACCESS_TOKEN,
    KEY_EXPIRES_AT,
    KEY_REFRESH_TOKEN,
    KEY_USER_ID,
    OAUTH_URL2,
    AuthenticationError,
    SensiConnectionError,
    refresh_access_token,
)
from custom_components.sensi.data import AuthenticationConfig
from homeassistant.core import HomeAssistant


class TestAuthenticationConfig:
    """Test cases for AuthenticationConfig class."""

    def test_authentication_config_init_all_fields(self):
        """Test AuthenticationConfig initialization with all fields."""
        config = AuthenticationConfig(
            user_id="user123",
            access_token="access_token_123",
            expires_at=1234567890.0,
            refresh_token="refresh_token_123",
        )
        assert config.user_id == "user123"
        assert config.access_token == "access_token_123"
        assert config.expires_at == 1234567890.0
        assert config.refresh_token == "refresh_token_123"

        headers = config.headers
        assert headers == {"Authorization": "bearer access_token_123"}

    def test_authentication_config_partial_init(self):
        """Test AuthenticationConfig initialization with default values."""
        config = AuthenticationConfig(
            refresh_token="refresh_token_123",
        )
        assert config.user_id is None
        assert config.access_token is None
        assert config.expires_at is None
        assert config.refresh_token == "refresh_token_123"

    def test_authentication_config_headers_multiple_calls_consistent(self):
        """Test headers property returns consistent value."""
        config = AuthenticationConfig(
            user_id="user123",
            access_token="access_token_123",
            expires_at=1234567890.0,
            refresh_token="refresh_token_123",
        )
        headers1 = config.headers
        headers2 = config.headers
        assert headers1 == headers2


@pytest.mark.parametrize(("message"), [("Test error message"), ("")])
def test_authentication_error(message) -> None:
    """Test AuthenticationError is an Exception."""
    error = AuthenticationError(message)
    assert isinstance(error, Exception)
    assert error.message == message


class TestSensiConnectionError:
    """Test cases for SensiConnectionError exception."""

    def test_sensi_connection_error_creation(self):
        """Test creating SensiConnectionError."""
        error = SensiConnectionError("Connection timeout")
        assert error.message == "Connection timeout"
        assert str(error) == "Connection timeout"

    def test_sensi_connection_error_is_exception(self):
        """Test SensiConnectionError is an Exception."""
        error = SensiConnectionError("Test")
        assert isinstance(error, Exception)

    def test_sensi_connection_error_with_empty_message(self):
        """Test SensiConnectionError with empty message."""
        error = SensiConnectionError("")
        assert error.message == ""

    def test_sensi_connection_error_can_be_raised_and_caught(self):
        """Test SensiConnectionError can be raised and caught."""
        with pytest.raises(SensiConnectionError) as exc_info:
            raise SensiConnectionError("Network error")
        assert exc_info.value.message == "Network error"

    def test_sensi_connection_error_different_from_authentication_error(self):
        """Test SensiConnectionError is different from AuthenticationError."""
        with pytest.raises(SensiConnectionError):
            raise SensiConnectionError("Connection failed")

        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Auth failed")

    def test_sensi_connection_error_message_with_timeout(self):
        """Test SensiConnectionError with timeout message."""
        error = SensiConnectionError("Timed out getting access token")
        assert error.message == "Timed out getting access token"

    def test_sensi_connection_error_message_with_network_details(self):
        """Test SensiConnectionError with network details."""
        error = SensiConnectionError("Failed to connect to oauth.sensiapi.io")
        assert error.message == "Failed to connect to oauth.sensiapi.io"


async def test_refresh_access_token(
    hass: HomeAssistant,
    mock_auth_data,
    aioclient_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test refresh_access_token function."""

    refresh_token = "refresh_token_123"

    # Return different value in POST request to simulate getting new access token
    expires_in = 3100
    json = {
        KEY_ACCESS_TOKEN: "new_access_token_999",
        KEY_REFRESH_TOKEN: "new_refresh_token_999",
        "expires_in": expires_in,
        KEY_USER_ID: "user123",
    }

    freezer.tick()
    expected_persistent_data = deepcopy(json)

    expected_persistent_data[KEY_EXPIRES_AT] = (
        datetime.now() + timedelta(seconds=expires_in)
    ).timestamp()
    expected_persistent_data.pop("expires_in")

    aioclient_mock.post(OAUTH_URL2, json=json)

    with (
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
        patch("homeassistant.helpers.storage.Store.async_save") as mock_async_save,
    ):
        result = await refresh_access_token(hass, refresh_token)

        mock_async_save.assert_called_once_with(expected_persistent_data)
        assert result is not None


async def test_refresh_access_token_post_failure(
    hass: HomeAssistant, mock_auth_data, aioclient_mock
) -> None:
    """Test refresh_access_token function."""

    refresh_token = "refresh_token_123"
    aioclient_mock.post(OAUTH_URL2, status=202)

    with (
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
        pytest.raises(AuthenticationError),
    ):
        await refresh_access_token(hass, refresh_token)


async def test_refresh_access_token_timeout(
    hass: HomeAssistant, mock_auth_data, aioclient_mock
) -> None:
    """Test refresh_access_token function."""

    refresh_token = "refresh_token_123"
    aioclient_mock.post(OAUTH_URL2, exc=TimeoutError)

    with (
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
        pytest.raises(SensiConnectionError),
    ):
        await refresh_access_token(hass, refresh_token)
