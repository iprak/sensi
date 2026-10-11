"""Tests for Sensi."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er


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


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_removes_unused_devices(
    hass: HomeAssistant, mock_coordinator, mock_auth_data
) -> None:
    """Test unused devices are removed after setup."""

    mock_entry = mock_coordinator.config_entry
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    unused_device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("sensi", "unused")},
    )
    used_device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("sensi", "used")},
    )
    entity_registry.async_get_or_create(
        "sensor",
        "sensi",
        "used_device_entity",
        config_entry=mock_entry,
        device_id=used_device.id,
    )

    with (
        patch(
            "custom_components.sensi.client.SensiClient.wait_for_devices"
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert device_registry.async_get(unused_device.id) is None
    assert device_registry.async_get(used_device.id) is not None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_init_keeps_devices_with_entities(
    hass: HomeAssistant, mock_coordinator, mock_auth_data
) -> None:
    """Test devices with entities are not removed during setup cleanup."""

    mock_entry = mock_coordinator.config_entry
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("sensi", "with_entity")},
    )
    entity_registry.async_get_or_create(
        "sensor",
        "sensi",
        "with_entity_sensor",
        config_entry=mock_entry,
        device_id=device.id,
    )

    with (
        patch(
            "custom_components.sensi.client.SensiClient.wait_for_devices"
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            return_value=mock_auth_data,
        ),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is not None
