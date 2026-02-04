"""Tests for Sensi number component."""

from unittest.mock import MagicMock, patch

from custom_components.sensi.client import ActionResponse
from custom_components.sensi.number import (
    NUMBER_TYPES,
    SensiNumberEntity,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant


async def test_setup_platform(
    hass: HomeAssistant,
    mock_entry,
    mock_coordinator,
    mock_device,
    mock_device_with_humidification,
) -> None:
    """Test platform setup."""

    mock_coordinator.get_devices = MagicMock(
        return_value=[mock_device, mock_device_with_humidification]
    )

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, async_add_entities)

    assert async_add_entities.called
    assert len(async_add_entities.call_args[0][0]) == 4


async def test_get_value(hass: HomeAssistant, mock_device, mock_coordinator) -> None:
    """Test native_value for humidity entity."""

    humidity_desc = next((s for s in NUMBER_TYPES if s.key == "humidity_offset"), None)
    entity = SensiNumberEntity(hass, mock_device, humidity_desc, mock_coordinator)

    value = 35
    mock_device.state.humidity_offset = value

    assert entity.native_value == value


async def test_native_unit_of_measurement(
    hass: HomeAssistant, mock_device, mock_coordinator
) -> None:
    """Test native_unit_of_measurement."""

    humidity_desc = next((s for s in NUMBER_TYPES if s.key == "humidity_offset"), None)
    entity1 = SensiNumberEntity(hass, mock_device, humidity_desc, mock_coordinator)
    assert (
        entity1.native_unit_of_measurement == humidity_desc.native_unit_of_measurement
    )

    temp_desc = next((s for s in NUMBER_TYPES if s.key == "temperature_offset"), None)
    entity2 = SensiNumberEntity(hass, mock_device, temp_desc, mock_coordinator)
    assert entity2.native_unit_of_measurement == mock_device.state.temperature_unit


async def test_set_value(hass: HomeAssistant, mock_device, mock_coordinator) -> None:
    """Test async_set_native_value for humidity entity."""

    humidity_desc = next((s for s in NUMBER_TYPES if s.key == "humidity_offset"), None)
    entity = SensiNumberEntity(hass, mock_device, humidity_desc, mock_coordinator)

    with (
        patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state,
        patch.object(mock_coordinator, "async_refresh") as mock_async_refresh,
        patch.object(
            mock_coordinator.client, "async_set_humidity_offset"
        ) as mock_async_set_humidity_offset,
    ):
        mock_async_set_humidity_offset.return_value = ActionResponse(None, {})

        # Pass float and verify that int is passed down to client
        await entity.async_set_native_value(50.0)

        mock_async_set_humidity_offset.assert_called_once_with(mock_device, 50)
        mock_async_write_ha_state.assert_called_once()
        mock_async_refresh.assert_called_once()
