"""Tests for Sensi binary_sensor component."""

from custom_components.sensi.binary_sensor import OnlineBinarySensorEntity
from custom_components.sensi.const import SENSI_ATTRIBUTION
from custom_components.sensi.entity import SensiDescriptionEntity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory


class TestOnlineBinarySensorEntity:
    """Test cases for OnlineBinarySensorEntity class."""

    def test_online_binary_sensor_initialization(self, mock_device, mock_coordinator):
        """Test OnlineBinarySensorEntity initialization."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )

        # Create a mock hass object
        hass = mock_coordinator.hass

        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity._device == mock_device
        assert entity.entity_description == description
        assert entity.coordinator == mock_coordinator

    def test_online_binary_sensor_is_on_true(self, mock_device, mock_coordinator):
        """Test is_on property returns True when device is online."""

        # Ensure status is "online"
        mock_device.state.status = "online"

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.is_on is True

    def test_online_binary_sensor_is_on_false(self, mock_device, mock_coordinator):
        """Test is_on property returns False when device is offline."""

        # Set status to offline
        mock_device.state.status = "offline"

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.is_on is False

    def test_online_binary_sensor_is_on_other_status(
        self, mock_device, mock_coordinator
    ):
        """Test is_on property with other status values."""

        mock_device.state.status = "unknown"

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.is_on is False

    def test_online_binary_sensor_is_on_empty_status(
        self, mock_device, mock_coordinator
    ):
        """Test is_on property with empty status."""

        mock_device.state.status = ""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.is_on is False

    def test_online_binary_sensor_description_attributes(self):
        """Test OnlineBinarySensorEntity description attributes."""
        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )

        assert description.key == "online"
        assert description.name == "Online"
        assert description.device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert description.entity_category == EntityCategory.DIAGNOSTIC
        assert description.entity_registry_enabled_default is False

    def test_online_binary_sensor_entity_description_type(
        self, mock_device, mock_coordinator
    ):
        """Test entity_description is properly set."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.entity_description is not None
        assert entity.entity_description.key == "online"
        assert entity.entity_description.name == "Online"

    def test_online_binary_sensor_device_info(self, mock_device, mock_coordinator):
        """Test that device info is properly inherited."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.device_info is not None
        # Device info may be a dict or DeviceInfo object
        device_info = entity.device_info
        assert device_info is not None

    def test_online_binary_sensor_unique_id(self, mock_device, mock_coordinator):
        """Test unique_id contains device identifier."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        # unique_id should contain the device identifier
        assert mock_device.identifier in entity.unique_id

    def test_online_binary_sensor_is_on_case_sensitivity(
        self, mock_device, mock_coordinator
    ):
        """Test is_on property is case-sensitive for 'online' check."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        # Test "Online" with capital O - should be False
        mock_device.state.status = "Online"
        assert entity.is_on is False

        # Test "ONLINE" - should be False
        mock_device.state.status = "ONLINE"
        assert entity.is_on is False

        # Test "online" - should be True
        mock_device.state.status = "online"
        assert entity.is_on is True

    def test_online_binary_sensor_state_changes(self, mock_device, mock_coordinator):
        """Test is_on changes when device state is updated."""

        mock_device.state.status = "online"

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )
        assert entity.is_on is True

        # Change device status
        mock_device.state.status = "offline"
        assert entity.is_on is False

        # Change back
        mock_device.state.status = "online"
        assert entity.is_on is True

    def test_online_binary_sensor_inherits_from_sensi_description_entity(
        self, mock_device, mock_coordinator
    ):
        """Test OnlineBinarySensorEntity inherits from SensiDescriptionEntity."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert isinstance(entity, SensiDescriptionEntity)
        assert isinstance(entity, BinarySensorEntity)

    def test_online_binary_sensor_has_entity_name(self, mock_device, mock_coordinator):
        """Test that has_entity_name is True (inherited from SensiEntity)."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.has_entity_name is True

    def test_online_binary_sensor_has_attribution(self, mock_device, mock_coordinator):
        """Test that attribution is set (inherited from SensiEntity)."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.attribution == SENSI_ATTRIBUTION

    def test_online_binary_sensor_coordinator_property(
        self, mock_device, mock_coordinator
    ):
        """Test coordinator property is accessible."""

        description = BinarySensorEntityDescription(
            key="online",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )

        hass = mock_coordinator.hass
        entity = OnlineBinarySensorEntity(
            hass, mock_device, description, mock_coordinator
        )

        assert entity.coordinator == mock_coordinator
