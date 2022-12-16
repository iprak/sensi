"""Sensi Thermostat authentication helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Final
import uuid

import aiohttp
import async_timeout
from homeassistant.helpers import aiohttp_client
from homeassistant.util.json import load_json, save_json

_LOGGER = logging.getLogger(__name__)

OAUTH_URL: Final = "https://oauth.sensiapi.io/token?device={}"
CLIENT_SECRET: Final = "XBF?Z9U6;x3bUwe^FugbL=4ksvGjLnCQ"
CLIENT_ID: Final = "android"


@dataclass
class AuthenticationConfig:
    """Internal Sensi authentication configuration."""

    username: str | None = None
    password: str | None = None
    scan_interval: timedelta | None = None
    access_token: str | None = None
    expires_at: float | None = None


async def login(hass, config: AuthenticationConfig, renew_token: bool = False) -> bool:
    """Login."""

    persistent_file = hass.config.path("sensi_device.json")
    persistent_data = load_json(persistent_file)
    device_id = persistent_data.get("device_id", uuid.uuid4())

    if not renew_token:
        access_token = persistent_data.get("access_token")
        refresh_token = persistent_data.get("refresh_token")
        expires_at = persistent_data.get("expires_at")

        if device_id and access_token and expires_at:
            config.access_token = access_token
            config.expires_at = expires_at

            _LOGGER.info("Using saved persistent data")
            return True

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
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timed out getting access token")
        return False

    if response.status != HTTPStatus.OK:
        _LOGGER.error("Error getting access token")
        return False

    response_json = await response.json()
    access_token = response_json.get("access_token")
    refresh_token = response_json.get("refresh_token")
    expires_in = int(response_json.get("expires_in"))
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).timestamp()

    config.access_token = access_token
    config.expires_at = expires_at

    persistent_data["device_id"] = device_id
    persistent_data["access_token"] = access_token
    persistent_data["refresh_token"] = refresh_token
    persistent_data["expires_at"] = expires_at

    save_json(persistent_file, persistent_data)
    return True
