"""Tests for Sensi authentication module."""

import pytest

from custom_components.sensi.auth import AuthenticationError, SensiConnectionError
from custom_components.sensi.data import AuthenticationConfig


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


class TestAuthenticationError:
    """Test cases for AuthenticationError exception."""

    def test_authentication_error_creation(self):
        """Test creating AuthenticationError."""
        error = AuthenticationError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_authentication_error_is_exception(self):
        """Test AuthenticationError is an Exception."""
        error = AuthenticationError("Test")
        assert isinstance(error, Exception)

    def test_authentication_error_with_empty_message(self):
        """Test AuthenticationError with empty message."""
        error = AuthenticationError("")
        assert error.message == ""

    def test_authentication_error_can_be_raised_and_caught(self):
        """Test AuthenticationError can be raised and caught."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Caught error")
        assert exc_info.value.message == "Caught error"

    def test_authentication_error_message_with_special_characters(self):
        """Test AuthenticationError with special characters in message."""
        message = "Error: Invalid credentials! Status: 401"
        error = AuthenticationError(message)
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
