"""The Sensi data coordinator."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import SensiConnectionError
from .client import SensiClient
from .const import COORDINATOR_UPDATE_INTERVAL, LOGGER
from .data import AuthenticationConfig, SensiDevice

type SensiConfigEntry = ConfigEntry[SensiUpdateCoordinator]


class SensiUpdateCoordinator(DataUpdateCoordinator):
    """The Sensi data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AuthenticationConfig,
        client: SensiClient,
    ) -> None:
        """Initialize Sensi coordinator."""

        self._config = config
        self._last_update_failed = False  # Used for debugging

        async def async_update_devices() -> None:
            """Update device data."""

            try:
                await self.client.async_update_devices()
            except SensiConnectionError as err:
                raise UpdateFailed from err

        super().__init__(
            hass,
            LOGGER,
            name="SensiUpdateCoordinator",
            update_method=async_update_devices,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

        self.client = client

    def get_devices(self) -> list[SensiDevice]:
        """Sensi devices."""
        return self.client.get_devices()

    # async def _verify_authentication(self) -> bool:
    #     """Verify that authentication is not expired. Login again if necessary."""
    #     if datetime.now().timestamp() >= self._expires_at:
    #         LOGGER.info("Token expired, getting new token")

    #         self._login_retry = self._login_retry + 1
    #         if self._login_retry > MAX_LOGIN_RETRY:
    #             LOGGER.info(
    #                 "Login failed %d times. Suspending data update", self._login_retry
    #             )
    #             self.update_interval = None
    #             return False

    #         try:
    #             await get_access_token(self.hass, self._auth_config, True)
    #             self._login_retry = 0
    #         except AuthenticationError:
    #             LOGGER.warning("Unable to authenticate", exc_info=True)
    #             return False
    #         except SensiConnectionError:
    #             LOGGER.warning("Failed to connect", exc_info=True)
    #             return False

    #         self._save_auth_config(self._auth_config)

    #     return True
