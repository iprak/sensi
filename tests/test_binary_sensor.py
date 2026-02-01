"""Tests for Sensi binary_sensor component."""

import pytest

from custom_components.sensi.binary_sensor import OnlineBinarySensorEntity
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


class TestOnlineBinarySensorEntity:
    """Test cases for OnlineBinarySensorEntity class."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [("online", True), ("ONLINE", True), ("offline", False), ("unknown", False)],
    )
    def test_online_binary_sensor(
        self, hass: HomeAssistant, mock_device, mock_coordinator, status, expected
    ):
        """Test is_on property returns True when device is online."""

        mock_device.state.status = status
        description = create_description()
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
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

    def test_online_binary_sensor_entity_description_type(
        self, hass: HomeAssistant, mock_device, mock_coordinator
    ):
        """Test entity_description is properly set."""

        description = create_description()
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.entity_description is not None
        assert entity.entity_description.key == "online"
        assert entity.entity_description.name == "Online"
        assert entity.device_info is not None
