import json
import os

import pytest

from custom_components.sensi.auth import AuthenticationConfig
from custom_components.sensi.coordinator import SensiUpdateCoordinator
from homeassistant.core import HomeAssistant


def load_json(filename):
    """Load sample JSON."""
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, encoding="utf-8") as fptr:
        return fptr.read()


@pytest.fixture(name="mock_coordinator")
def create_mock_crumb_coordinator(hass: HomeAssistant) -> SensiUpdateCoordinator:
    """Fixture to provide a test instance of CrumbCoordinator."""
    config = AuthenticationConfig()
    config.access_token = "access_token"
    config.expires_at = 12345
    config.refresh_token = "refresh_token"
    return SensiUpdateCoordinator(hass, config)


@pytest.fixture
def mock_json():
    """Return sample JSON data."""
    return json.loads(load_json("sample.json"))
