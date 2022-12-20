"""The Sensi data coordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import logging
from multiprocessing import AuthenticationError
from typing import Final

from homeassistant.components.climate import HVACMode
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import websockets

from custom_components.sensi.auth import (
    AuthenticationConfig,
    SensiConnectionError,
    login,
)
from custom_components.sensi.const import SENSI_FAN_CIRCULATE

_LOGGER = logging.getLogger(__name__)

WS_URL: Final = "wss://rt.sensiapi.io/thermostat/?transport=websocket"
MAX_LOGIN_RETRY: Final = 4

SENSI_TO_HVACMode = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.AUTO,
    "off": HVACMode.OFF,
}

HA_TO_SENSI_HVACMode = {
    HVACMode.HEAT: "heat",
    HVACMode.COOL: "cool",
    HVACMode.AUTO: "auto",
    HVACMode.OFF: "off",
}


class SensiDevice:
    """Class representing a Sensi thermostat device."""

    # pylint: disable=too-many-instance-attributes
    # These attributes are meant to be here.

    coordinator: SensiUpdateCoordinator = None

    identifier: str | None = None
    name: str | None = None
    model: str | None = None

    temperature: float | None = None
    humidity: int | None = None
    hvac_mode: HVACMode = HVACMode.AUTO
    temperature_unit = TEMP_FAHRENHEIT

    _display_scale = "f"
    """Raw display_scale"""

    fan_mode: str | None = None
    attributes: dict[str, str | float] = {}
    min_temp = 45
    max_temp = 99
    cool_target: float | None = None
    heat_target: float | None = None

    def __init__(self, coordinator, data_json):
        """Initialize a Sensi thermostate device."""
        self.coordinator = coordinator
        self.update(data_json)

    @staticmethod
    def data_has_state(device_data) -> bool:
        """Check if the data has device state."""
        return "state" in device_data

    def update(self, data_json):
        """Update device properties."""
        self.identifier = data_json.get("icd_id")

        # if self.identifier is None:
        # error

        self.identifier = self.identifier.lower()

        registration = data_json.get("registration")
        if registration:
            self.name = registration.get("name", "No Name")
            self.model = registration.get("product_type")

        state = data_json.get("state")
        if state:
            _LOGGER.info("Updating %s (%s)", self.name, self.identifier)
            _LOGGER.debug(state)

            if "display_temp" in state:
                self.temperature = state.get("display_temp")

            if "humidity" in state:
                self.humidity = state.get("humidity")

            # current_operating_mode can be auto_heat but operating_mode remains auto
            if "operating_mode" in state:
                self._operating_mode = state.get("operating_mode")
                self.hvac_mode = SENSI_TO_HVACMode.get(
                    self._operating_mode, HVACMode.AUTO
                )

            if "display_scale" in state:
                self._display_scale = state.get("display_scale")
                self.temperature_unit = (
                    TEMP_CELSIUS if self._display_scale == "c" else TEMP_FAHRENHEIT
                )

            self.attributes["wifi_connection_quality"] = state.get(
                "wifi_connection_quality"
            )
            self.attributes["battery_voltage"] = state.get("battery_voltage")

            self.min_temp = state.get("cool_min_temp", 45)
            self.max_temp = state.get("heat_max_temp", 99)

            self.cool_target = state.get("current_cool_temp")
            self.heat_target = state.get("current_heat_temp")

            demand_status = state.get("demand_status", {"heat": 0, "cool": 0})
            hvac_action = None
            if demand_status["heat"] > 0:
                hvac_action = "heating"
            if demand_status["cool"] > 0:
                hvac_action = "cooling"
            self.attributes["hvac_action"] = hvac_action

            # Fan mode is on or auto. We will create a third mode circulate which is based on auto.
            if "fan_mode" in state:
                self.fan_mode = state.get("fan_mode")

            circulating_fan = state.get(
                "circulating_fan", {"enabled": "off", "duty_cycle": 0}
            )
            self.attributes["circulating_fan"] = circulating_fan["enabled"]
            self.attributes["circulating_fan_cuty_cycle"] = circulating_fan[
                "duty_cycle"
            ]
            if self.attributes["circulating_fan"] == "on":
                self.fan_mode = SENSI_FAN_CIRCULATE

            _LOGGER.info(
                "%d%s humidity=%d hvac_mode=%s fan_mode=%s hvac_action=%s",
                self.temperature,
                self.temperature_unit,
                self.humidity,
                self.hvac_mode,
                self.fan_mode,
                hvac_action,
            )

    async def async_set_temp(self, value: int) -> None:
        """Set the target temperature."""

        # com.emerson.sensi.api.events.SetTemperatureEvent > set_temperature
        data = [
            "set_temperature",
            {
                "icd_id": self.identifier,
                "target_temp": value,
                "mode": self._operating_mode.lower(),
                "scale": self._display_scale,
            },
        ]
        await self.coordinator.async_send_event(json.dumps(data))

        # Assume the operation to succeed, update attribute immediately
        self.temperature = value

    async def async_set_fan_mode(self, mode: str) -> None:
        """Set the fan mode."""

        # com.emerson.sensi.api.events.SetFanModeEvent > set_fan_mode
        data = [
            "set_fan_mode",
            {
                "icd_id": self.identifier,
                "value": mode.lower(),
            },
        ]

        await self.coordinator.async_send_event(json.dumps(data))

        # Assume the operation to succeed, update attribute immediately
        self.fan_mode = mode

    async def async_set_circulating_fan_mode(
        self, enabled: bool, duty_cycle: int
    ) -> None:
        """Set the circulating fan mode."""

        status = "on" if enabled else "off"
        # com.emerson.sensi.api.events.SetCirculatingFanEvent > set_fan_mode
        data = [
            "set_circulating_fan",
            {
                "icd_id": self.identifier,
                "value": {"enabled": status, "duty_cycle": duty_cycle},
            },
        ]

        await self.coordinator.async_send_event(json.dumps(data))

        # Assume the operation to succeed, update attribute immediately
        self.attributes["circulating_fan"] = status
        self.attributes["circulating_fan_cuty_cycle"] = duty_cycle

    async def async_set_operating_mode(self, mode: str) -> None:
        """Set the fan mode."""

        # com.emerson.sensi.api.events.SetSystemModeEvent > "set_operating_mode"
        data = [
            "set_operating_mode",
            {
                "icd_id": self.identifier,
                "value": mode,
            },
        ]
        await self.coordinator.async_send_event(json.dumps(data))

        # Assume the operation to succeed, update attribute immediately
        self.hvac_mode = SENSI_TO_HVACMode.get(mode, HVACMode.AUTO)


# async def async_set_heat_max_temp(self, value) -> None:
#     """Set the maximum temperature."""
#     data = [
#         "set_heat_max_temp",
#         {
#             "icd_id": self._device.identifier,
#             "value": round(value),
#             "scale": self._device.display_scale,
#         },
#     ]
#     await self.coordinator.async_send_event(json.dumps(data))


class SensiUpdateCoordinator(DataUpdateCoordinator):
    """The Sensi data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AuthenticationConfig,
    ) -> None:
        """Initialize Sensi coordinator."""

        self._hass = hass
        self._auth_config: AuthenticationConfig = None
        self._devices: dict[str, SensiDevice] = {}
        self._login_retry = 0

        self._setup(config)

        super().__init__(
            hass,
            _LOGGER,
            name="SensiUpdateCoordinator",
            update_interval=timedelta(seconds=30),
        )

    def _setup(self, config: AuthenticationConfig):
        self._auth_config = config
        self._access_token = config.access_token
        self._headers = {"Authorization": "bearer " + config.access_token}
        self._expires_at = config.expires_at

    def get_devices(self) -> list[SensiDevice]:
        """Sensi devices."""
        return self._devices.values()

    def get_device(self, icd_id):
        """Return a specific Sensi device."""
        return self._devices.get(icd_id)

    def _parse_socket_response(self, msg: str, devices: dict[str, SensiDevice]) -> bool:
        """Parse the websocket device response."""
        if not msg or not msg.startswith("42"):
            return False

        found_data = False
        parsed_json = json.loads(msg[2:])
        if parsed_json[0] == "state":
            for device_data in parsed_json[1]:
                icd_id = device_data.get("icd_id")

                # Assuimg that data will be present for all devices in consistent manner.
                found_data = SensiDevice.data_has_state(device_data)

                if icd_id in devices:
                    devices[icd_id].update(device_data)
                else:
                    _LOGGER.info("Creating device %s", icd_id)
                    devices[icd_id] = SensiDevice(self, device_data)

        return found_data

    async def _async_update_data(self) -> dict[str, SensiDevice]:
        """Update device data. This is invoked by DataUpdateCoordinator."""
        if datetime.now().timestamp() >= self._expires_at:
            _LOGGER.info("Token expired, getting new token")

            self._login_retry = self._login_retry + 1
            if self._login_retry > MAX_LOGIN_RETRY:
                _LOGGER.info(
                    "Login failed %d times. Suspending data update.", self._login_retry
                )
                self.update_interval = None
                return

            try:
                await login(self._hass, self._auth_config, True)
                self._login_retry = 0
            except AuthenticationError:
                _LOGGER.warning("Unable to authenticate", exc_info=True)
                return
            except SensiConnectionError:
                _LOGGER.warning("Failed to connect", exc_info=True)
                return

            self._setup(self._auth_config)

        async with websockets.connect(WS_URL, extra_headers=self._headers) as websocket:
            done = False
            while not done:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                    done = self._parse_socket_response(msg, self._devices)

                except asyncio.TimeoutError:
                    _LOGGER.warning("Timed out waiting for data")
                    done = True
                except websockets.exceptions.WebSocketException as socket_exception:
                    _LOGGER.warning(str(socket_exception))
                    done = True
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.warning(str(err))
                    done = True

        return self._devices

    async def async_send_event(self, data: str):
        """Send a JSON request."""
        async with websockets.connect(WS_URL, extra_headers=self._headers) as websocket:
            try:
                await websocket.send("421" + data)
                msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                _LOGGER.debug("async_send_event response=%s", msg)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.warning("Sending event with %s failed", data)
                _LOGGER.warning(str(err))
