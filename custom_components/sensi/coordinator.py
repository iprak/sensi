"""The Sensi data coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
from multiprocessing import AuthenticationError
from typing import Any, Final

import websockets.client

from .auth import (
    AuthenticationConfig,
    SensiConnectionError,
    login,
)
from .const import (
    CAPABILITIES_VALUE_GETTER,
    COORDINATOR_DELAY_REFRESH_AFTER_UPDATE,
    COORDINATOR_UPDATE_INTERVAL,
    LOGGER,
    SENSI_FAN_CIRCULATE,
    Capabilities,
    Settings,
)
from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# This is based on IOWrapper.java
# pylint: disable=line-too-long
WS_URL: Final = "wss://rt.sensiapi.io/thermostat/?transport=websocket"
CAPABILITIES_PARAM = "display_humidity,fan_mode_settings,continuous_backlight,degrees_fc,display_time,circulating_fan,operating_mode_settings"

# All possible capabilities:
# display_humidity,operating_mode_settings,fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,outdoor_stages,
# continuous_backlight,degrees_fc,display_time,keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,
# heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,
# max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,humidity_control,humidity_offset,humidity_offset_lower_bound,
# humidity_offset_upper_bound,temp_offset_lower_bound,temp_offset_upper_bound,lowest_heat_setpoint_ceiling,heat_setpoint_ceiling,
# highest_cool_setpoint_floor,cool_setpoint_floor"

# pylint: enable=line-too-long

MAX_LOGIN_RETRY: Final = 4
MAX_DATA_FETCH_COUNT: Final = 5

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


def parse_bool(state: dict[str, Any], key: str) -> bool | None:
    """Parse on/off into bool value."""
    if key in state:
        return state.get(key) == "on"
    else:
        return None


def calculate_battery_level(voltage: float) -> int | None:
    """Calculate the battery level."""
    # https://devzone.nordicsemi.com/f/nordic-q-a/28101/how-to-calculate-battery-voltage-into-percentage-for-aa-2-batteries-without-fluctuations
    # https://forum.arduino.cc/t/calculate-battery-percentage-of-alkaline-batteries-using-the-voltage/669958/17
    if voltage is None:
        return None
    mvolts = voltage * 1000
    # return "low" if (((voltage * 1000) - 900) * 100) / (600) <= 30 else "good"
    if mvolts >= 3000:
        return 100
    elif mvolts > 2900:
        return 100 - int(((3000 - mvolts) * 58) / 100)
    elif mvolts > 2740:
        return 42 - int(((2900 - mvolts) * 24) / 160)
    elif mvolts > 2440:
        return 18 - int(((2740 - mvolts) * 12) / 300)
    elif mvolts > 2100:
        return 6 - int(((2440 - mvolts) * 6) / 340)
    else:
        return 0


class SensiDevice:
    """Class representing a Sensi thermostat device."""

    # pylint: disable=too-many-instance-attributes
    # These attributes are meant to be here.

    coordinator = None

    identifier: str | None = None
    name: str | None = None
    model: str | None = None

    temperature: float | None = None
    temperature_unit = UnitOfTemperature.FAHRENHEIT
    humidity: int | None = None
    hvac_mode: HVACMode = HVACMode.AUTO

    _display_scale = "f"
    """Raw display_scale"""

    _capabilities: dict[Capabilities, bool] = None
    _properties: dict[Settings, StateType] = None

    fan_mode: str | None = None
    attributes: dict[str, str | float] = None
    min_temp = 45
    max_temp = 99
    cool_target: float | None = None
    heat_target: float | None = None
    battery_voltage: float | None = None
    battery_level: int | None = None
    offline: bool = True

    def __init__(self, coordinator, data_json: dict) -> None:
        """Initialize a Sensi thermostate device."""

        self._capabilities = {}
        self._properties = {}
        self.attributes = {}

        self.coordinator = coordinator
        self.update(data_json)

    def update_capabilities(self, data: dict):
        """Update device capabilities."""

        for key in Capabilities:
            # key can be property.sub_property
            prop_name = key.split(".")[0]
            getter = CAPABILITIES_VALUE_GETTER.get(key)
            if getter:
                value = getter(data.get(prop_name))
            else:
                value = data.get(prop_name, "no")

            self._capabilities[key] = value == "yes"

        LOGGER.debug("%s Capabilities=%s", self.name, json.dumps(self._capabilities))

    def supports(self, value: Capabilities) -> bool:
        """Check if the device has the capability."""
        return self._capabilities.get(value, False)

    def update(self, data_json: dict):
        """Update device properties."""
        self.identifier = data_json.get("icd_id").lower()

        registration = data_json.get("registration")
        if registration:
            self.name = registration.get("name", "No Name")
            self.model = registration.get("product_type")

        state = data_json.get("state")
        if state:
            LOGGER.info("Updating %s (%s)", self.name, self.identifier)
            LOGGER.debug(state)

            self.offline = state.get("status") == "offline"
            self.attributes["offline"] = self.offline

            self.temperature = state.get("display_temp")
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
                    UnitOfTemperature.CELSIUS
                    if self._display_scale == "c"
                    else UnitOfTemperature.FAHRENHEIT
                )

            self.attributes["wifi_connection_quality"] = state.get(
                "wifi_connection_quality"
            )
            self.battery_voltage = state.get("battery_voltage")
            self.attributes["battery_voltage"] = self.battery_voltage
            self.battery_level = calculate_battery_level(self.battery_voltage)

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

            if self.supports(Capabilities.CIRCULATING_FAN) and (
                "circulating_fan" in state
            ):
                circulating_fan = state.get(
                    "circulating_fan", {"enabled": "off", "duty_cycle": 0}
                )
                self.attributes["circulating_fan"] = circulating_fan["enabled"]
                self.attributes["circulating_fan_cuty_cycle"] = circulating_fan[
                    "duty_cycle"
                ]

                if self.attributes["circulating_fan"] == "on":
                    self.fan_mode = SENSI_FAN_CIRCULATE

            self._properties[Settings.CONTINUOUS_BACKLIGHT] = parse_bool(
                state, Settings.CONTINUOUS_BACKLIGHT
            )
            self._properties[Settings.DISPLAY_HUMIDITY] = parse_bool(
                state, Settings.DISPLAY_HUMIDITY
            )
            self._properties[Settings.DISPLAY_TIME] = parse_bool(
                state, Settings.DISPLAY_TIME
            )

            # pylint: disable=line-too-long
            LOGGER.info(
                "%d%s humidity=%d hvac_mode=%s fan_mode=%s hvac_action=%s cool_target=%d heat_target=%d",
                self.temperature,
                self.temperature_unit,
                self.humidity,
                self.hvac_mode,
                self.fan_mode,
                hvac_action,
                self.cool_target,
                self.heat_target,
            )
            # pylint: enable=line-too-long

    async def async_set_temp(self, value: int) -> None:
        """Set the target temperature."""

        if self.hvac_mode == HVACMode.HEAT:
            if self.heat_target == value:
                return
        elif self.cool_target == value:
            return

        # com.emerson.sensi.api.events.SetTemperatureEvent > set_temperature
        data = self.build_set_request_str(
            "temperature",
            {
                "target_temp": value,
                "mode": self._operating_mode.lower(),
                "scale": self._display_scale,
            },
        )
        await self.coordinator.async_send_event(data)

        if self.hvac_mode == HVACMode.HEAT:
            self.heat_target = value
        else:
            self.cool_target = value

    async def async_set_fan_mode(self, mode: str) -> None:
        """Set the fan mode."""

        mode = mode.lower()
        if self.fan_mode == mode:
            return

        # com.emerson.sensi.api.events.SetFanModeEvent > set_fan_mode
        data = self.build_set_request_str("fan_mode", {"value": mode})
        await self.coordinator.async_send_event(data)
        self.fan_mode = mode

    async def async_set_circulating_fan_mode(
        self, enabled: bool, duty_cycle: int
    ) -> None:
        """Set the circulating fan mode."""

        if not self.supports(Capabilities.CIRCULATING_FAN):
            LOGGER.info(
                "%s: circulating fan mode was set but the device does not support it",
                self.identifier,
            )
            return

        status = "on" if enabled else "off"

        if (self.attributes["circulating_fan"] == status) and (
            self.attributes["circulating_fan_cuty_cycle"] == duty_cycle
        ):
            return

        # com.emerson.sensi.api.events.SetCirculatingFanEvent > set_fan_mode
        data = self.build_set_request_str(
            "circulating_fan",
            {"value": {"enabled": status, "duty_cycle": duty_cycle}},
        )
        await self.coordinator.async_send_event(data)

        self.attributes["circulating_fan"] = status
        self.attributes["circulating_fan_cuty_cycle"] = duty_cycle

    async def async_set_operating_mode(self, mode: str) -> None:
        """Set the fan mode.

        com.emerson.sensi.api.events.SetSystemModeEvent > "set_operating_mode".
        """

        new_hvac_mode = SENSI_TO_HVACMode.get(mode, HVACMode.AUTO)
        if new_hvac_mode == self.hvac_mode:
            return

        data = self.build_set_request_str("operating_mode", {"value": mode})
        await self.coordinator.async_send_event(data)
        self.hvac_mode = new_hvac_mode

    def get_setting(self, key: Settings) -> bool | None:
        """Get a display configuration."""
        return self._properties.get(key)

    async def async_set_setting(self, key: Settings, value: bool) -> None:
        """Set a display configuration."""

        if key not in Settings:
            raise ValueError(f"Unsupported setting: {key}")

        if value == self.get_setting(key):
            return

        data = self.build_set_request_str(key, {"value": "on" if value else "off"})
        await self.coordinator.async_send_event(data)
        self._properties[key] = value

    def build_set_request_str(self, key: str, payload: dict[str, str]) -> str:
        """Prepare the request string for setting data."""

        data = payload.copy()
        data["icd_id"] = self.identifier
        json_data = [f"set_{key}", data]
        return json.dumps(json_data)


class SensiUpdateCoordinator(DataUpdateCoordinator):
    """The Sensi data update coordinator."""

    _last_event_time_stamp: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: AuthenticationConfig,
    ) -> None:
        """Initialize Sensi coordinator."""

        self._auth_config: AuthenticationConfig = None
        self._devices: dict[str, SensiDevice] = {}
        self._login_retry = 0
        self._last_update_failed = False

        self._save_auth_config(config)

        super().__init__(
            hass,
            LOGGER,
            name="SensiUpdateCoordinator",
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

    def _save_auth_config(self, config: AuthenticationConfig):
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

        found_state = False

        parsed_json = json.loads(msg[2:])
        if parsed_json[0] == "state":
            for device_data in parsed_json[1]:
                icd_id = device_data.get("icd_id")

                # Assumes that data will be present for all devices in consistent manner.
                found_state = "state" in device_data

                if icd_id in devices:
                    devices[icd_id].update(device_data)
                else:
                    LOGGER.info("Creating device %s", icd_id)
                    devices[icd_id] = SensiDevice(self, device_data)

                if "capabilities" in device_data:
                    devices[icd_id].update_capabilities(device_data["capabilities"])

        return found_state

    async def _async_update_data(self) -> dict[str, SensiDevice]:
        """Update device data. This is invoked by DataUpdateCoordinator."""

        # Testing showed that update after a event request failed to bring new data.
        # The next update would bring in correct data, skipping update conditionally.
        if self._last_event_time_stamp is not None:
            if (datetime.now() - self._last_event_time_stamp) < timedelta(
                seconds=COORDINATOR_DELAY_REFRESH_AFTER_UPDATE
            ):
                return self._devices

        if not await self._verify_authentication():
            return self._devices

        url = f"{WS_URL}&capabilities={CAPABILITIES_PARAM}"

        fetch_count = 0
        done = False

        async with websockets.client.connect(
            url, extra_headers=self._headers
        ) as websocket:
            while (not done) and (fetch_count < MAX_DATA_FETCH_COUNT):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=10)
                    done = self._parse_socket_response(msg, self._devices)
                    fetch_count = fetch_count + 1

                    if self._last_update_failed:
                        LOGGER.debug("Data updated, it failed last time")
                        self._last_update_failed = False

                except asyncio.TimeoutError:
                    LOGGER.warning("Timed out waiting for data")
                    done = True
                    self._last_update_failed = True
                except websockets.exceptions.WebSocketException as socket_exception:
                    LOGGER.warning(str(socket_exception))
                    self._last_update_failed = True
                    done = True
                except Exception as err:  # pylint: disable=broad-except
                    LOGGER.warning(str(err))
                    self._last_update_failed = True
                    done = True

        return self._devices

    async def async_send_event(self, data: str) -> None:
        """Send a JSON request."""

        await self.async_send_event_priv(data)
        await self.async_send_event_priv(data)  # Repeat

    async def async_send_event_priv(self, data: str) -> None:
        """Send a JSON request."""

        self._last_event_time_stamp = None

        async with websockets.client.connect(
            WS_URL, extra_headers=self._headers
        ) as websocket:
            try:
                await websocket.send("421" + data)
                msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                # self._last_event_time_stamp = datetime.now()
                LOGGER.debug("async_send_event response=%s", msg)
            except Exception as err:  # pylint: disable=broad-except
                LOGGER.warning("Sending event with %s failed", data)
                LOGGER.warning(str(err))

    async def _verify_authentication(self) -> bool:
        """Verify that authentication is not expired. Login again if necessary."""
        if datetime.now().timestamp() >= self._expires_at:
            LOGGER.info("Token expired, getting new token")

            self._login_retry = self._login_retry + 1
            if self._login_retry > MAX_LOGIN_RETRY:
                LOGGER.info(
                    "Login failed %d times. Suspending data update", self._login_retry
                )
                self.update_interval = None
                return False

            try:
                await login(self.hass, self._auth_config, True)
                self._login_retry = 0
            except AuthenticationError:
                LOGGER.warning("Unable to authenticate", exc_info=True)
                return False
            except SensiConnectionError:
                LOGGER.warning("Failed to connect", exc_info=True)
                return False

            self._save_auth_config(self._auth_config)

        return True
