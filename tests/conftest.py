"""Fixtures for Sensi tests."""

import json
import os
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sensi.auth import AuthenticationConfig
from custom_components.sensi.client import SensiClient
from custom_components.sensi.climate import SensiThermostat
from custom_components.sensi.const import SENSI_DOMAIN
from custom_components.sensi.coordinator import SensiDevice, SensiUpdateCoordinator
from homeassistant.core import HomeAssistant


# from homeassistant import config_entries
def load_json(filename):
    """Load sample JSON."""
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, encoding="utf-8") as fptr:
        return fptr.read()


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> SensiUpdateCoordinator:
    """Fixture to provide a test instance of CrumbCoordinator."""
    config = AuthenticationConfig(
        refresh_token="refresh_token",
        access_token="access_token",
        expires_at=12345,
        user_id="user_id",
    )
    client = SensiClient(hass, config, MagicMock())
    return SensiUpdateCoordinator(hass, client)


@pytest.fixture
def mock_json():
    """Return sample JSON data."""
    return json.loads(load_json("sample.json"))


@pytest.fixture
def mock_json_with_humidification():
    """Return sample JSON data with humidification."""
    return json.loads(load_json("sample_with_humidification.json"))


@pytest.fixture
def mock_device(mock_json) -> SensiDevice:
    """Create a mock SensiDevice from sample JSON data."""
    _have_state, device = SensiDevice.create(mock_json)
    return device


@pytest.fixture
def mock_device_with_humidification(mock_json_with_humidification) -> SensiDevice:
    """Create a mock SensiDevice with humidification support."""
    _have_state, device = SensiDevice.create(mock_json_with_humidification)
    return device


@pytest.fixture
def mock_entry(hass: HomeAssistant, mock_coordinator) -> MockConfigEntry:
    """Create a mock Config entry."""
    # config_entries.ConfigEntry
    entry = MockConfigEntry(domain=SENSI_DOMAIN, data={}, entry_id="id1")
    entry.runtime_data = mock_coordinator
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_thermostat(mock_device, mock_entry, mock_coordinator) -> SensiThermostat:
    """Create a mock SensiThermostat."""
    return SensiThermostat(mock_device, mock_entry, mock_coordinator)


@pytest.fixture
def mock_thermostat_with_humidification(
    mock_device_with_humidification, mock_entry, mock_coordinator
) -> SensiThermostat:
    """Create a mock SensiThermostat with humidification."""
    return SensiThermostat(
        mock_device_with_humidification, mock_entry, mock_coordinator
    )
