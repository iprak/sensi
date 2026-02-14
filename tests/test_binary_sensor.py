"""Tests for Sensi binary_sensor component."""

from unittest.mock import MagicMock

import pytest

from custom_components.sensi.binary_sensor import (
    OnlineBinarySensorEntity,
    async_setup_entry,
)
from custom_components.sensi.coordinator import SensiUpdateCoordinator
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant


def create_description() -> BinarySensorEntityDescription:
    """Create a test BinarySensorEntityDescription."""
    return BinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_setup_platform(
    hass: HomeAssistant,
    mock_coordinator: SensiUpdateCoordinator,
    mock_device,
    mock_device_with_humidification,
) -> None:
    """Test platform setup."""

    mock_coordinator.get_devices = MagicMock(
        return_value=[mock_device, mock_device_with_humidification]
    )

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_coordinator.config_entry, async_add_entities)

    assert async_add_entities.called
    assert len(async_add_entities.call_args[0][0]) == 2  # 1 per device


class TestOnlineBinarySensorEntity:
    """Test cases for OnlineBinarySensorEntity class."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [("online", True), ("ONLINE", True), ("offline", False), ("unknown", False)],
    )
    def test_online_binary_sensor(
        self,
        hass: HomeAssistant,
        mock_device,
        mock_coordinator: SensiUpdateCoordinator,
        status,
        expected,
    ):
        """Test is_on property returns True when device is online."""

        mock_device.state.status = status
        description = create_description()
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator.config_entry
        )

        assert entity.is_on == expected

    def test_online_binary_sensor_description_attributes(self):
        """Test OnlineBinarySensorEntity description attributes."""
        description = create_description()

        assert description.key == "online"
        assert description.name == "Online"
        assert description.device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert description.entity_category == EntityCategory.DIAGNOSTIC
        assert description.entity_registry_enabled_default is False

    def test_online_binary_sensor_available(
        self, hass: HomeAssistant, mock_device, mock_coordinator: SensiUpdateCoordinator
    ):
        """Test OnlineBinarySensorEntity available."""

        description = create_description()
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator.config_entry
        )
        mock_coordinator.last_update_success = False

        assert entity.available is False

    def test_online_binary_sensor_entity_description_type(
        self, hass: HomeAssistant, mock_device, mock_coordinator: SensiUpdateCoordinator
    ):
        """Test entity_description is properly set."""

        description = create_description()
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator.config_entry
        )

        assert entity.entity_description is not None
        assert entity.entity_description.key == "online"
        assert entity.entity_description.name == "Online"
        assert entity.device_info is not None
