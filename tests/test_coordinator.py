"""Tests for Sensi coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from custom_components.sensi.auth import AuthenticationConfig
from custom_components.sensi.client import SensiClient
from custom_components.sensi.const import COORDINATOR_UPDATE_INTERVAL
from custom_components.sensi.coordinator import SensiUpdateCoordinator
from custom_components.sensi.data import SensiDevice
from homeassistant.core import HomeAssistant


class TestSensiUpdateCoordinatorInitialization:
    """Test cases for SensiUpdateCoordinator initialization."""

    def test_coordinator_initialization(self, hass: HomeAssistant):
        """Test SensiUpdateCoordinator initialization."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator.hass == hass
        assert coordinator.client == client
        assert coordinator._config == config

    def test_coordinator_name(self, hass: HomeAssistant):
        """Test coordinator has correct name."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator.name == "SensiUpdateCoordinator"

    def test_coordinator_update_interval(self, hass: HomeAssistant):
        """Test coordinator has correct update interval."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        expected_interval = timedelta(seconds=COORDINATOR_UPDATE_INTERVAL)
        assert coordinator.update_interval == expected_interval

    def test_coordinator_last_update_failed_initialized_false(
        self, hass: HomeAssistant
    ):
        """Test that _last_update_failed is initialized to False."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator._last_update_failed is False


class TestSensiUpdateCoordinatorHeaders:
    """Test cases for SensiUpdateCoordinator header setup."""

    def test_setup_headers_creates_authorization_header(self, hass: HomeAssistant):
        """Test that _setup_headers creates correct Authorization header."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access_token_123",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        expected_header = "bearer test_access_token_123"
        assert coordinator._headers["Authorization"] == expected_header

    def test_setup_headers_uses_access_token_from_config(self, hass: HomeAssistant):
        """Test that headers use the access token from config."""
        config = AuthenticationConfig(
            refresh_token="refresh_123",
            access_token="access_456",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert "bearer access_456" in coordinator._headers["Authorization"]

    def test_setup_headers_format_includes_bearer_prefix(self, hass: HomeAssistant):
        """Test that Authorization header includes 'bearer' prefix."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="token123",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator._headers["Authorization"].startswith("bearer ")


class TestSensiUpdateCoordinatorGetDevices:
    """Test cases for SensiUpdateCoordinator.get_devices()."""

    def test_get_devices_returns_client_devices(self, hass: HomeAssistant, mock_json):
        """Test that get_devices returns devices from client."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        have_state, device = SensiDevice.create(mock_json)

        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = [device]

        coordinator = SensiUpdateCoordinator(hass, config, client)
        devices = coordinator.get_devices()

        assert len(devices) == 1
        assert devices[0] == device

    def test_get_devices_returns_empty_list_when_no_devices(self, hass: HomeAssistant):
        """Test that get_devices returns empty list when no devices."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []

        coordinator = SensiUpdateCoordinator(hass, config, client)
        devices = coordinator.get_devices()

        assert devices == []

    def test_get_devices_returns_multiple_devices(self, hass: HomeAssistant, mock_json):
        """Test that get_devices returns multiple devices."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        have_state1, device1 = SensiDevice.create(mock_json)
        have_state2, device2 = SensiDevice.create(mock_json)

        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = [device1, device2]

        coordinator = SensiUpdateCoordinator(hass, config, client)
        devices = coordinator.get_devices()

        assert len(devices) == 2
        assert devices[0] == device1
        assert devices[1] == device2

    def test_get_devices_calls_client_get_devices(self, hass: HomeAssistant):
        """Test that get_devices calls client.get_devices()."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []

        coordinator = SensiUpdateCoordinator(hass, config, client)
        coordinator.get_devices()

        client.get_devices.assert_called_once()


class TestSensiUpdateCoordinatorUpdateMethod:
    """Test cases for SensiUpdateCoordinator update method."""

    def test_update_method_exists(self, hass: HomeAssistant):
        """Test that coordinator has an update method."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        # Coordinator should have update_method attribute from DataUpdateCoordinator
        assert hasattr(coordinator, "update_method")

    def test_update_interval_is_timedelta(self, hass: HomeAssistant):
        """Test that update_interval is a timedelta object."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert isinstance(coordinator.update_interval, timedelta)

    def test_update_interval_matches_const(self, hass: HomeAssistant):
        """Test that update interval matches the const value."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        expected = timedelta(seconds=COORDINATOR_UPDATE_INTERVAL)
        assert coordinator.update_interval == expected


class TestSensiUpdateCoordinatorConfig:
    """Test cases for SensiUpdateCoordinator configuration."""

    def test_coordinator_stores_config(self, hass: HomeAssistant):
        """Test that coordinator stores the config."""
        config = AuthenticationConfig(
            refresh_token="refresh_token_value",
            access_token="access_token_value",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator._config == config
        assert coordinator._config.refresh_token == "refresh_token_value"
        assert coordinator._config.access_token == "access_token_value"

    def test_coordinator_config_properties_accessible(self, hass: HomeAssistant):
        """Test that config properties are accessible through coordinator."""
        config = AuthenticationConfig(
            refresh_token="my_refresh_token",
            access_token="my_access_token",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator._config.refresh_token == "my_refresh_token"
        assert coordinator._config.access_token == "my_access_token"


class TestSensiUpdateCoordinatorClient:
    """Test cases for SensiUpdateCoordinator client management."""

    def test_coordinator_stores_client(self, hass: HomeAssistant):
        """Test that coordinator stores the client."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator.client == client

    def test_coordinator_client_is_accessible(self, hass: HomeAssistant):
        """Test that client is accessible from coordinator."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)
        client.test_property = "test_value"

        coordinator = SensiUpdateCoordinator(hass, config, client)

        assert coordinator.client.test_property == "test_value"

    def test_coordinator_can_call_client_methods(self, hass: HomeAssistant):
        """Test that coordinator can call client methods."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []

        coordinator = SensiUpdateCoordinator(hass, config, client)
        coordinator.client.get_devices()

        client.get_devices.assert_called_once()


class TestSensiUpdateCoordinatorIntegration:
    """Integration tests for SensiUpdateCoordinator."""

    def test_coordinator_full_initialization_flow(self, hass: HomeAssistant):
        """Test full initialization flow."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []

        coordinator = SensiUpdateCoordinator(hass, config, client)

        # Verify all components initialized correctly
        assert coordinator.hass == hass
        assert coordinator.client == client
        assert coordinator._config == config
        assert coordinator.name == "SensiUpdateCoordinator"
        assert "Authorization" in coordinator._headers
        assert coordinator.get_devices() == []

    def test_coordinator_with_different_access_tokens(self, hass: HomeAssistant):
        """Test coordinator with different access tokens."""
        configs = [
            AuthenticationConfig(refresh_token="refresh1", access_token="access1"),
            AuthenticationConfig(refresh_token="refresh2", access_token="access2"),
        ]

        for config in configs:
            client = MagicMock(spec=SensiClient)
            coordinator = SensiUpdateCoordinator(hass, config, client)

            expected_auth = f"bearer {config.access_token}"
            assert coordinator._headers["Authorization"] == expected_auth

    def test_coordinator_properties_are_immutable(self, hass: HomeAssistant):
        """Test that coordinator properties persist correctly."""
        config = AuthenticationConfig(
            refresh_token="test_refresh",
            access_token="test_access",
        )
        client = MagicMock(spec=SensiClient)

        coordinator = SensiUpdateCoordinator(hass, config, client)

        # Store references
        original_config = coordinator._config
        original_client = coordinator.client

        # Get devices to ensure no side effects
        coordinator.get_devices()

        # Verify references didn't change
        assert coordinator._config is original_config
        assert coordinator.client is original_client
