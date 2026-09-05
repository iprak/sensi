"""The Sensi data coordinator."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import AuthenticationError, SensiConnectionError
from .client import SensiClient
from .const import COORDINATOR_UPDATE_INTERVAL, LOGGER
from .data import SensiDevice

type SensiConfigEntry = ConfigEntry[SensiUpdateCoordinator]


class SensiUpdateCoordinator(DataUpdateCoordinator):
    """The Sensi data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SensiClient,
        config_entry: SensiConfigEntry,
    ) -> None:
        """Initialize Sensi coordinator."""

        self._consecutive_failed_count = 0

        async def async_update_devices() -> None:
            """Update device data."""

            try:
                await self.client.async_update_devices()
                self._consecutive_failed_count = 0
            except AuthenticationError as err:
                # The refresh token itself is invalid, trigger HA's reauth flow
                # instead of retrying forever.
                raise ConfigEntryAuthFailed from err
            except SensiConnectionError as err:
                self._consecutive_failed_count += 1
                LOGGER.info(
                    "Failed to connect to Sensi API, consecutive failed count: %d",
                    self._consecutive_failed_count,
                )
                raise UpdateFailed(str(err)) from err

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="SensiUpdateCoordinator",
            update_method=async_update_devices,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

        self.client = client

    def get_devices(self) -> list[SensiDevice]:
        """Sensi devices."""
        return self.client.get_devices()

    @property
    def consecutive_connection_failures(self) -> int:
        """Return the number of consecutive failed updates."""
        return self._consecutive_failed_count

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
