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


def test_update(mock_json) -> None:
    """Test update of SensiDevice."""
    device = SensiDevice(mock_json)
    assert device.state.fan_mode == FanMode.ON
