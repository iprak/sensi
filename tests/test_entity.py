"""Tests for Sensi entity module."""

from custom_components.sensi.const import SENSI_ATTRIBUTION, SENSI_DOMAIN
from custom_components.sensi.entity import SensiDescriptionEntity, SensiEntity
from homeassistant.helpers.entity import EntityDescription


class TestSensiEntity:
    """Test cases for SensiEntity class."""

    def test_sensi_entity_init(self, mock_device, mock_coordinator):
        """Test SensiEntity initialization."""
        entity = SensiEntity(mock_device, mock_coordinator.config_entry)

        assert entity._device == mock_device
        assert entity.coordinator == mock_coordinator
        assert entity.has_entity_name is True
        assert entity.attribution == SENSI_ATTRIBUTION
        assert entity.unique_id == mock_device.identifier

    def test_sensi_entity_device_info(self, mock_coordinator, mock_device):
        """Test SensiEntity device info is correctly set."""
        entity = SensiEntity(mock_device, mock_coordinator.config_entry)

        device_info = entity.device_info
        assert device_info["identifiers"] == {(SENSI_DOMAIN, mock_device.identifier)}
        assert device_info["name"] == mock_device.name
        assert device_info["manufacturer"] == "Sensi"
        assert device_info["model"] == mock_device.info.model_number
        assert device_info["serial_number"] == mock_device.info.serial_number

    def test_sensi_entity_unique_id_uses_device_identifier(
        self, mock_coordinator, mock_device
    ):
        """Test SensiEntity unique_id is based on device identifier."""
        entity = SensiEntity(mock_device, mock_coordinator.config_entry)

        assert entity.unique_id == mock_device.identifier


class TestSensiDescriptionEntity:
    """Test cases for SensiDescriptionEntity class."""

    def test_sensi_description_entity_init(self, mock_device, mock_coordinator):
        """Test SensiDescriptionEntity initialization."""
        description = EntityDescription(key="test_key")
        entity = SensiDescriptionEntity(
            mock_device, description, mock_coordinator.config_entry
        )

        assert entity._device == mock_device
        assert entity.coordinator == mock_coordinator
        assert entity.entity_description == description
        assert entity.has_entity_name is True
        assert entity.attribution == SENSI_ATTRIBUTION

    def test_sensi_description_entity_unique_id_includes_description_key(
        self, mock_device, mock_coordinator
    ):
        """Test SensiDescriptionEntity unique_id includes description key."""
        description = EntityDescription(key="custom_key")
        entity = SensiDescriptionEntity(
            mock_device, description, mock_coordinator.config_entry
        )

        expected_unique_id = f"{mock_device.identifier}_custom_key"
        assert entity.unique_id == expected_unique_id

    def test_sensi_description_entity_different_keys_create_different_ids(
        self, mock_coordinator, mock_device
    ):
        """Test different description keys create different unique IDs."""
        description1 = EntityDescription(key="key1")
        description2 = EntityDescription(key="key2")
        mock_entry = mock_coordinator.config_entry

        entity1 = SensiDescriptionEntity(mock_device, description1, mock_entry)
        entity2 = SensiDescriptionEntity(mock_device, description2, mock_entry)

        assert entity1.unique_id != entity2.unique_id
        assert "key1" in entity1.unique_id
        assert "key2" in entity2.unique_id

    def test_sensi_description_entity_device_info(self, mock_coordinator, mock_device):
        """Test SensiDescriptionEntity device info is correctly set."""
        description = EntityDescription(key="test_key")
        entity = SensiDescriptionEntity(
            mock_device, description, mock_coordinator.config_entry
        )

        device_info = entity.device_info
        assert device_info["identifiers"] == {(SENSI_DOMAIN, mock_device.identifier)}
        assert device_info["name"] == mock_device.name
        assert device_info["manufacturer"] == "Sensi"

    def test_sensi_description_entity_with_special_characters_in_key(
        self, mock_coordinator, mock_device
    ):
        """Test SensiDescriptionEntity creation."""
        description = EntityDescription(key="test_key_with_underscores")
        entity = SensiDescriptionEntity(
            mock_device, description, mock_coordinator.config_entry
        )

        assert isinstance(entity, SensiEntity)
        expected_unique_id = f"{mock_device.identifier}_test_key_with_underscores"
        assert entity.unique_id == expected_unique_id
