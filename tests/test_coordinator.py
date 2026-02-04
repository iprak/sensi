"""Tests for Sensi coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from custom_components.sensi.client import SensiClient
from custom_components.sensi.const import COORDINATOR_UPDATE_INTERVAL
from custom_components.sensi.coordinator import SensiUpdateCoordinator
from custom_components.sensi.data import SensiDevice
from homeassistant.core import HomeAssistant


class TestSensiUpdateCoordinatorInitialization:
    """Test cases for SensiUpdateCoordinator initialization."""

    def test_coordinator_initialization(self, hass: HomeAssistant):
        """Test SensiUpdateCoordinator initialization."""

        client = MagicMock(spec=SensiClient)
        coordinator = SensiUpdateCoordinator(hass, client)

        assert coordinator.hass == hass
        assert coordinator.client == client
        assert coordinator.name == "SensiUpdateCoordinator"

    def test_coordinator_update_interval(self, hass: HomeAssistant):
        """Test coordinator has correct update interval."""
        client = MagicMock(spec=SensiClient)
        coordinator = SensiUpdateCoordinator(hass, client)

        expected_interval = timedelta(seconds=COORDINATOR_UPDATE_INTERVAL)
        assert coordinator.update_interval == expected_interval


class TestSensiUpdateCoordinatorGetDevices:
    """Test cases for SensiUpdateCoordinator.get_devices()."""

    def test_get_devices_returns_client_devices(self, hass: HomeAssistant, mock_json):
        """Test that get_devices returns devices from client."""
        _have_state1, device1 = SensiDevice.create(mock_json)
        _have_state2, device2 = SensiDevice.create(mock_json)

        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = [device1, device2]

        coordinator = SensiUpdateCoordinator(hass, client)
        devices = coordinator.get_devices()

        assert len(devices) == 2
        assert devices[0] == device1
        assert devices[1] == device2

    def test_get_devices_returns_empty_list_when_no_devices(self, hass: HomeAssistant):
        """Test that get_devices returns empty list when no devices."""
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []

        coordinator = SensiUpdateCoordinator(hass, client)
        devices = coordinator.get_devices()

        assert devices == []


class TestSensiUpdateCoordinatorIntegration:
    """Integration tests for SensiUpdateCoordinator."""

    def test_coordinator_properties_are_immutable(self, hass: HomeAssistant):
        """Test that coordinator properties persist correctly."""
        client = MagicMock(spec=SensiClient)
        coordinator = SensiUpdateCoordinator(hass, client)

        # Store references
        original_client = coordinator.client

        # Get devices to ensure no side effects
        coordinator.get_devices()

        # Verify references didn't change
        assert coordinator.client is original_client
