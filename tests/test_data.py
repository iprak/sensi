"""Tests for Sensi data component."""

from custom_components.sensi.coordinator import SensiDevice
from custom_components.sensi.data import DemandStatus, FanMode, State


def test_demand_status_parsing(mock_json) -> None:
    """Test DemandStatus parsing using sample.json."""
    state_dict = mock_json.get("state", {})
    state_obj = State(state_dict)

    assert isinstance(state_obj.demand_status, DemandStatus)
    assert state_obj.demand_status.fan == 0
    assert state_obj.demand_status.last == "heat"


def test_sensi_device_create_with_state(mock_json) -> None:
    """Test SensiDevice.create with valid state data."""
    have_state, device = SensiDevice.create(mock_json)

    assert have_state is True
    assert device.identifier == mock_json.get("icd_id")
    assert device.name == mock_json.get("registration", {}).get("name")
    assert isinstance(device.state, State)


def test_sensi_device_create_without_state(mock_json) -> None:
    """Test SensiDevice.create without state data."""
    data = {
        "icd_id": "test-id",
        "registration": {"name": "Test Device"},
        "capabilities": {},
        "thermostat_info": {},
    }

    have_state, device = SensiDevice.create(data)

    assert have_state is False
    assert device.identifier == "test-id"


def test_sensi_device_create_missing_fields(mock_json) -> None:
    """Test SensiDevice.create with missing optional fields."""
    data = {"icd_id": "test-id"}

    have_state, device = SensiDevice.create(data)

    assert have_state is False
    assert device.identifier == "test-id"
    assert device.name == ""


