"""Sensi Thermostat authentication helpers."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Final
import uuid

import aiohttp
import async_timeout

from .const import LOGGER, STORAGE_KEY, STORAGE_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, storage

# Defined in CreateRefreshParams.java
OAUTH_URL: Final = "https://oauth.sensiapi.io/token?device={}"
CLIENT_SECRET: Final = "XBF?Z9U6;x3bUwe^FugbL=4ksvGjLnCQ"

# The following constants are mentioned in AuthenticationService.java
CLIENT_ID: Final = "android"
KEY_DEVICE_ID: Final = "device_id"
KEY_ACCESS_TOKEN: Final = "access_token"
KEY_REFRESH_TOKEN: Final = "refresh_token"
KEY_EXPIRES_AT: Final = "expires_at"


@dataclass
class AuthenticationConfig:
    """Internal Sensi authentication configuration."""

    username: str | None = None
    password: str | None = None
    scan_interval: timedelta | None = None
    access_token: str | None = None
    expires_at: float | None = None


async def login(
    hass: HomeAssistant, config: AuthenticationConfig, new_token: bool = False
):
    """Login."""

    store = storage.Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    persistent_data = await store.async_load() or {}
    device_id = persistent_data.get(KEY_DEVICE_ID)

    if not new_token:
        access_token = persistent_data.get(KEY_ACCESS_TOKEN)
        refresh_token = persistent_data.get(KEY_REFRESH_TOKEN)
        expires_at = persistent_data.get(KEY_EXPIRES_AT)

        if device_id and access_token and expires_at:
            config.access_token = access_token
            config.expires_at = expires_at

            LOGGER.debug("Using saved authentication")
            return

    if not device_id:
        device_id = uuid.uuid4()
        persistent_data[KEY_DEVICE_ID] = device_id

    post_data = {
        "username": config.username,
        "password": config.password,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "password",
    }

    try:
        session = aiohttp_client.async_get_clientsession(hass)
        async with async_timeout.timeout(10):
            response = await session.post(OAUTH_URL.format(device_id), data=post_data)
    except (asyncio.TimeoutError, aiohttp.ClientError) as err:
        LOGGER.warning("Timed out getting access token", exc_info=True)
        raise SensiConnectionError from err

    persistent_data["device_id"] = device_id

    # Uncomment this to test async_step_reauth
    # raise AuthenticationError("Invalid login credentials")
    if response.status != HTTPStatus.OK:
        await store.async_save(persistent_data)
        raise AuthenticationError("Invalid login credentials")

    response_json = await response.json()
    access_token = response_json.get(KEY_ACCESS_TOKEN)
    refresh_token = response_json.get(KEY_REFRESH_TOKEN)
    expires_in = int(response_json.get("expires_in"))
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).timestamp()

    config.access_token = access_token
    config.expires_at = expires_at

    persistent_data[KEY_ACCESS_TOKEN] = access_token
    persistent_data[KEY_REFRESH_TOKEN] = refresh_token
    persistent_data[KEY_EXPIRES_AT] = expires_at

    await store.async_save(persistent_data)
    return


class AuthenticationError(Exception):
    """API exception occurred when fail to authenticate."""

    def __init__(self, message: str) -> None:
        """Create instance of AuthenticationError."""
        self.message = message
        super().__init__(self.message)


class SensiConnectionError(Exception):
    """API exception occurred when fail to connect."""

    def __init__(self, message: str) -> None:
        """Create instance of SensiConnectionError."""
        self.message = message
        super().__init__(self.message)
