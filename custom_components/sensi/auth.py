"""Sensi Thermostat authentication helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Final

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, storage

from .const import LOGGER, STORAGE_KEY, STORAGE_VERSION

DEFAULT_TIMEOUT = 10

# Defined in CreateRefreshParams.java
OAUTH_URL: Final = "https://oauth.sensiapi.io/token?device={}"
CLIENT_SECRET: Final = "XBF?Z9U6;x3bUwe^FugbL=4ksvGjLnCQ"

# The following constants are mentioned in AuthenticationService.java
CLIENT_ID: Final = "android"
KEY_DEVICE_ID: Final = "device_id"
KEY_ACCESS_TOKEN: Final = "access_token"
KEY_REFRESH_TOKEN: Final = "refresh_token"
KEY_EXPIRES_AT: Final = "expires_at"
KEY_USER_ID: Final = "user_id"

CLIENT_ID2: Final = "fleet"
CLIENT_SECRET2: Final = (
    "JLFjJmketRhj>M9uoDhusYKyi?zUyNqhGB)H2XiwLEF#KcGKrRD2JZsDQ7ufNven"
)
OAUTH_URL2: Final = "https://oauth.sensiapi.io/token"


@dataclass
class AuthenticationConfig:
    """Internal Sensi authentication configuration."""

    user_id: str | None = None
    access_token: str | None = None
    expires_at: float | None = None
    refresh_token: str | None = None


async def _get_new_tokens(hass: HomeAssistant, refresh_token: str) -> any:
    """Obtain new access_token and refresh_token for the given refresh_token."""

    result = {}
    LOGGER.debug("Getting access token using refresh_token=%s", refresh_token)

    post_data = {
        "client_id": CLIENT_ID2,
        "client_secret": CLIENT_SECRET2,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "accept-language": "en-US,en;q=0.9",
        "accept": "*/*",
    }

    try:
        session = aiohttp_client.async_get_clientsession(hass)
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                OAUTH_URL2,
                data=post_data,
                headers=headers,
                allow_redirects=True,
            )
    except (TimeoutError, aiohttp.ClientError) as err:
        LOGGER.warning("Timed out getting access token", exc_info=True)
        raise SensiConnectionError("Timed out getting access token") from err

    if response.status != HTTPStatus.OK:
        LOGGER.warning("Invalid token")
        raise AuthenticationError("Invalid token")

    response_json = await response.json()
    result[KEY_ACCESS_TOKEN] = response_json.get(KEY_ACCESS_TOKEN)
    result[KEY_REFRESH_TOKEN] = response_json.get(KEY_REFRESH_TOKEN)
    result[KEY_USER_ID] = response_json.get(
        KEY_USER_ID
    )  # This is used as unique_id in config flow

    expires_in = int(response_json.get("expires_in"))
    result[KEY_EXPIRES_AT] = (
        datetime.now() + timedelta(seconds=expires_in)
    ).timestamp()

    return result


# def get_device_id(persistent_data: any) -> str:
#     device_id = persistent_data.get(KEY_DEVICE_ID)
#     if not device_id:
#         device_id = uuid.uuid4()
#         persistent_data[KEY_DEVICE_ID] = device_id

#     return device_id


# async def get_stored_config(hass: HomeAssistant) -> AuthenticationConfig:
#     """Retrieve stored configuration. This will throw AuthenticationError for missing data."""

#     store = storage.Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
#     persistent_data = await store.async_load()

#     # Data can be missing in older installations, use get()
#     if refresh_token is None:
#         refresh_token = persistent_data.get(KEY_REFRESH_TOKEN)
#         if refresh_token is None:
#             raise AuthenticationError("Stored config is missing refresh_token")

#     result = await _get_new_tokens(hass, refresh_token)

#     persistent_data[KEY_ACCESS_TOKEN] = result[KEY_ACCESS_TOKEN]
#     persistent_data[KEY_REFRESH_TOKEN] = result[KEY_REFRESH_TOKEN]
#     persistent_data[KEY_EXPIRES_AT] = result[KEY_EXPIRES_AT]
#     persistent_data[KEY_USER_ID] = result[KEY_USER_ID]

#     # Only dict or simple values can be saved into store
#     await store.async_save(persistent_data)

#     return AuthenticationConfig(
#         user_id=persistent_data[KEY_USER_ID],
#         access_token=persistent_data[KEY_ACCESS_TOKEN],
#         expires_at=persistent_data[KEY_EXPIRES_AT],
#         refresh_token=persistent_data[KEY_REFRESH_TOKEN],
#     )


async def refresh_access_token(
    hass: HomeAssistant, refresh_token: str | None = None
) -> AuthenticationConfig:
    """Obtain new access_token and refresh_token for the given/stored refresh_token."""

    store = storage.Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    persistent_data = await store.async_load()
    if persistent_data is None:
        persistent_data = {}

    # Data can be missing in older installations, use get()
    if refresh_token is None:
        refresh_token = persistent_data.get(KEY_REFRESH_TOKEN)
        LOGGER.debug("Using stored refresh_token %s", refresh_token)
    else:
        LOGGER.debug("Using supplied refresh_token %s", refresh_token)

    if refresh_token is None:
        raise AuthenticationError("Stored config is missing refresh_token")

    result = await _get_new_tokens(hass, refresh_token)

    persistent_data[KEY_ACCESS_TOKEN] = result[KEY_ACCESS_TOKEN]
    persistent_data[KEY_REFRESH_TOKEN] = result[KEY_REFRESH_TOKEN]
    persistent_data[KEY_EXPIRES_AT] = result[KEY_EXPIRES_AT]
    persistent_data[KEY_USER_ID] = result[KEY_USER_ID]

    # Only dict or simple values can be saved into store
    await store.async_save(persistent_data)

    return AuthenticationConfig(
        user_id=persistent_data[KEY_USER_ID],
        access_token=persistent_data[KEY_ACCESS_TOKEN],
        expires_at=persistent_data[KEY_EXPIRES_AT],
        refresh_token=persistent_data[KEY_REFRESH_TOKEN],
    )


# async def login(
#     hass: HomeAssistant, config: AuthenticationConfig, new_token: bool = False
# ):
#     """Login."""

#     store = storage.Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
#     persistent_data = await store.async_load() or {}
#     device_id = persistent_data.get(KEY_DEVICE_ID)

#     if not new_token:
#         access_token = persistent_data.get(KEY_ACCESS_TOKEN)
#         refresh_token = persistent_data.get(KEY_REFRESH_TOKEN)
#         expires_at = persistent_data.get(KEY_EXPIRES_AT)

#         if device_id and access_token and expires_at:
#             config.access_token = access_token
#             config.expires_at = expires_at

#             LOGGER.debug("Using saved authentication")
#             return

#     if not device_id:
#         device_id = uuid.uuid4()
#         persistent_data[KEY_DEVICE_ID] = device_id

#     post_data = {
#         "username": config.username,
#         "password": config.password,
#         "client_id": CLIENT_ID,
#         "client_secret": CLIENT_SECRET,
#         "grant_type": "password",
#     }

#     headers = {
#         "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
#         "x-platform": "android",
#         "accept": "*/*",
#     }

#     try:
#         session = aiohttp_client.async_get_clientsession(hass)
#         async with asyncio.timeout(DEFAULT_TIMEOUT):
#             response = await session.post(
#                 OAUTH_URL.format(device_id),
#                 data=post_data,
#                 headers=headers,
#                 allow_redirects=True,
#             )
#     except (asyncio.TimeoutError, aiohttp.ClientError) as err:
#         LOGGER.warning("Timed out getting access token", exc_info=True)
#         raise SensiConnectionError from err

#     persistent_data["device_id"] = device_id

#     # Uncomment this to test async_step_reauth
#     # raise AuthenticationError("Invalid login credentials")
#     if response.status != HTTPStatus.OK:
#         await store.async_save(persistent_data)
#         raise AuthenticationError("Invalid login credentials")

#     response_json = await response.json()
#     access_token = response_json.get(KEY_ACCESS_TOKEN)
#     refresh_token = response_json.get(KEY_REFRESH_TOKEN)
#     expires_in = int(response_json.get("expires_in"))
#     expires_at = (datetime.now() + timedelta(seconds=expires_in)).timestamp()

#     config.access_token = access_token
#     config.expires_at = expires_at

#     persistent_data[KEY_ACCESS_TOKEN] = access_token
#     persistent_data[KEY_REFRESH_TOKEN] = refresh_token
#     persistent_data[KEY_EXPIRES_AT] = expires_at

#     await store.async_save(persistent_data)
#     return


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
