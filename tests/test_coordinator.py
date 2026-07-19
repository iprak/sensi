"""Tests for Sensi coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sensi.auth import AuthenticationError, SensiConnectionError
from custom_components.sensi.client import SensiClient
from custom_components.sensi.const import COORDINATOR_UPDATE_INTERVAL, SENSI_DOMAIN
from custom_components.sensi.coordinator import SensiUpdateCoordinator
from custom_components.sensi.data import SensiDevice
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


def test_coordinator_initialization(hass: HomeAssistant) -> None:
    """Test SensiUpdateCoordinator initialization."""

    client = MagicMock(spec=SensiClient)
    mock_entry = MockConfigEntry(domain=SENSI_DOMAIN, data={}, entry_id="id1")
    coordinator = SensiUpdateCoordinator(hass, client, mock_entry)

    assert coordinator.hass == hass
    assert coordinator.client == client
    assert coordinator.name == "SensiUpdateCoordinator"

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
        mock_entry = MockConfigEntry(domain=SENSI_DOMAIN, data={}, entry_id="id1")

        coordinator = SensiUpdateCoordinator(hass, client, mock_entry)
        devices = coordinator.get_devices()

        assert len(devices) == 2
        assert devices[0] == device1
        assert devices[1] == device2

    def test_get_devices_returns_empty_list_when_no_devices(self, hass: HomeAssistant):
        """Test that get_devices returns empty list when no devices."""
        client = MagicMock(spec=SensiClient)
        client.get_devices.return_value = []
        mock_entry = MockConfigEntry(domain=SENSI_DOMAIN, data={}, entry_id="id1")

        coordinator = SensiUpdateCoordinator(hass, client, mock_entry)
        devices = coordinator.get_devices()

        assert devices == []


class TestSensiUpdateCoordinatorIntegration:
    """Integration tests for SensiUpdateCoordinator."""

    def test_coordinator_properties_are_immutable(self, hass: HomeAssistant):
        """Test that coordinator properties persist correctly."""

        client = MagicMock(spec=SensiClient)
        mock_entry = MockConfigEntry(domain=SENSI_DOMAIN, data={}, entry_id="id1")
        coordinator = SensiUpdateCoordinator(hass, client, mock_entry)

        # Store references
        original_client = coordinator.client

        # Get devices to ensure no side effects
        coordinator.get_devices()

        # Verify references didn't change
        assert coordinator.client is original_client


class TestCoordinatorUpdateErrorMapping:
    """Test how the coordinator maps client errors during an update."""

    async def test_auth_error_maps_to_config_entry_auth_failed(
        self, mock_coordinator
    ) -> None:
        """A bad refresh token surfaces as ConfigEntryAuthFailed (triggers reauth)."""
        mock_coordinator.client.async_update_devices = AsyncMock(
            side_effect=AuthenticationError("bad refresh")
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await mock_coordinator.update_method()

    async def test_connection_error_maps_to_update_failed(
        self, mock_coordinator
    ) -> None:
        """A transient connection error surfaces as UpdateFailed (retry + backoff)."""
        mock_coordinator.client.async_update_devices = AsyncMock(
            side_effect=SensiConnectionError("down")
        )

        with pytest.raises(UpdateFailed):
            await mock_coordinator.update_method()

    async def test_success_does_not_raise(self, mock_coordinator) -> None:
        """A successful update does not raise."""
        mock_coordinator.client.async_update_devices = AsyncMock(return_value=None)

        await mock_coordinator.update_method()
