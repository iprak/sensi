"""Tests for Sensi."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_failed_missing_refresh_token(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test AuthenticationConfig initialization with all fields."""

    mock_config = {}
    mock_entry = mock_coordinator.config_entry

    with patch(
        "homeassistant.helpers.storage.Store.async_load", return_value=mock_config
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_auth_failed(
    hass: HomeAssistant, mock_coordinator, mock_auth_data
) -> None:
    """Test AuthenticationConfig initialization with authentication failure."""

    mock_entry = mock_coordinator.config_entry

    with (
        patch(
            "custom_components.sensi.client.SensiClient.wait_for_devices"
        ) as mock_wait_for_devices,
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
    ):
        mock_wait_for_devices.side_effect = ConfigEntryAuthFailed("Mocked exception")

        assert await hass.config_entries.async_setup(mock_entry.entry_id) is False
        mock_wait_for_devices.assert_called_once()
        assert mock_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_exception_retry(
    hass: HomeAssistant, mock_coordinator, mock_auth_data
) -> None:
    """Test AuthenticationConfig initialization with exception."""

    mock_entry = mock_coordinator.config_entry

    with (
        patch(
            "custom_components.sensi.client.SensiClient.wait_for_devices"
        ) as mock_wait_for_devices,
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
    ):
        mock_wait_for_devices.side_effect = Exception("Mocked exception")

        assert await hass.config_entries.async_setup(mock_entry.entry_id) is False
        mock_wait_for_devices.assert_called_once()
        assert mock_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_success(
    hass: HomeAssistant, mock_coordinator, mock_auth_data
) -> None:
    """Test AuthenticationConfig initialization with all fields."""

    mock_entry = mock_coordinator.config_entry

    with (
        patch(
            "custom_components.sensi.client.SensiClient.wait_for_devices"
        ) as mock_wait_for_devices,
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        mock_wait_for_devices.assert_called_once()
        assert mock_entry.state is ConfigEntryState.LOADED
