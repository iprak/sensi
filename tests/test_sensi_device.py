"""Tests for SensiDevice."""

from custom_components.sensi.const import SENSI_FAN_ON
from custom_components.sensi.coordinator import SensiDevice


def test_update(mock_coordinator, mock_json) -> None:
    """Test update of SensiDevice."""
    device = SensiDevice(mock_coordinator, mock_json)
    assert device.fan_mode == SENSI_FAN_ON
