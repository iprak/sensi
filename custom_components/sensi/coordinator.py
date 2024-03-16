"""The Sensi data coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
from multiprocessing import AuthenticationError
from typing import Any, Final

import websockets.client

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import AuthenticationConfig
from .const import (
    ATTR_BATTERY_VOLTAGE,
    ATTR_CIRCULATING_FAN,
    ATTR_CIRCULATING_FAN_DUTY_CYCLE,
    ATTR_OFFLINE,
    ATTR_POWER_STATUS,
    ATTR_WIFI_QUALITY,
    CAPABILITIES_VALUE_GETTER,
    COOL_MIN_TEMPERATURE,
    COORDINATOR_DELAY_REFRESH_AFTER_UPDATE,
    COORDINATOR_UPDATE_INTERVAL,
    HEAT_MAX_TEMPERATURE,
    LOGGER,
    OPERATING_MODE_TO_HVAC_MODE,
    SENSI_FAN_CIRCULATE,
    Capabilities,
    OperatingModes,
    Settings,
)

# This is based on IOWrapper.java
# pylint: disable=line-too-long
WS_URL: Final = "wss://rt.sensiapi.io/thermostat/?transport=websocket"
CAPABILITIES_PARAM = "display_humidity,fan_mode_settings,continuous_backlight,degrees_fc,display_time,circulating_fan,operating_mode_settings,keypad_lockout"

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


def parse_bool(state: dict[str, Any], key: str) -> bool | None:
    """Parse on/off into bool value."""
    if key in state:
        return state.get(key) == "on"

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
    if mvolts > 2900:
        return 100 - int(((3000 - mvolts) * 58) / 100)
    if mvolts > 2740:
        return 42 - int(((2900 - mvolts) * 24) / 160)
    if mvolts > 2440:
        return 18 - int(((2740 - mvolts) * 12) / 300)
    if mvolts > 2100:
        return 6 - int(((2440 - mvolts) * 6) / 340)

    return 0


class SensiDevice:
    """Class representing a Sensi thermostat device."""

    # pylint: disable=too-many-instance-attributes
    # These attributes are meant to be here.

    coordinator: SensiUpdateCoordinator | None = None

    identifier: str | None = None
    name: str | None = None
    model: str | None = None

    temperature: float | None = None
    temperature_unit = UnitOfTemperature.FAHRENHEIT
    humidity: int | None = None
    hvac_mode: HVACMode | None = None
    hvac_action: HVACAction | None = None

    last_action_heat: bool
    """Was the last action heating?"""

    operating_mode: OperatingModes | None = None
    """Operating mode reported by Sensi"""

    effective_operating_mode: OperatingModes | None = None

    _display_scale = "f"
    """Raw display_scale"""

    _capabilities: dict[Capabilities, bool] = None
    _properties: dict[Settings, StateType] = None

    fan_mode: str | None = None
    attributes: dict[str, str | float] = None
    min_temp = COOL_MIN_TEMPERATURE
    max_temp = HEAT_MAX_TEMPERATURE
    cool_target: float | None = None
    heat_target: float | None = None
    battery_level: int | None = None
    offline: bool = True

    # List of setters can be found in the enum SetSettingsEventNames (SetSettingsEventNames.java)

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

        # LOGGER.debug("%s Capabilities=%s", self.name, json.dumps(self._capabilities))

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
            self.attributes[ATTR_OFFLINE] = self.offline

            self.temperature = state.get("display_temp")
            self.humidity = state.get("humidity")

            self.parse_thermostat_mode_action(state)

            if "display_scale" in state:
                self._display_scale = state.get("display_scale")
                self.temperature_unit = (
                    UnitOfTemperature.CELSIUS
                    if self._display_scale == "c"
                    else UnitOfTemperature.FAHRENHEIT
                )
            else:
                LOGGER.info("Property 'display_scale' not found in data")

            self.attributes[ATTR_POWER_STATUS] = state.get("power_status")
            self.attributes[ATTR_WIFI_QUALITY] = state.get("wifi_connection_quality")

            battery_voltage = state.get("battery_voltage")
            self.attributes[ATTR_BATTERY_VOLTAGE] = battery_voltage
            self.battery_level = calculate_battery_level(battery_voltage)

            self.min_temp = state.get("cool_min_temp", COOL_MIN_TEMPERATURE)
            self.max_temp = state.get("heat_max_temp", HEAT_MAX_TEMPERATURE)

            self.cool_target = state.get("current_cool_temp")
            self.heat_target = state.get("current_heat_temp")

            # Fan mode is on or auto. We will create a third mode circulate which is based on auto.
            if "fan_mode" in state:
                self.fan_mode = state.get("fan_mode")

            if self.supports(Capabilities.CIRCULATING_FAN) and (
                "circulating_fan" in state
            ):
                circulating_fan = state.get(
                    "circulating_fan", {"enabled": "off", "duty_cycle": 0}
                )
                self.attributes[ATTR_CIRCULATING_FAN] = circulating_fan["enabled"]
                self.attributes[ATTR_CIRCULATING_FAN_DUTY_CYCLE] = circulating_fan[
                    "duty_cycle"
                ]

                if self.attributes[ATTR_CIRCULATING_FAN] == "on":
                    self.fan_mode = SENSI_FAN_CIRCULATE

            for key in Settings:
                self._properties[key] = parse_bool(state, key)

            # pylint: disable=line-too-long
            LOGGER.info(
                "%d%s humidity=%d, hvac_mode=%s, fan_mode=%s, hvac_action=%s, cool_target=%d, heat_target=%d",
                self.temperature,
                self.temperature_unit,
                self.humidity,
                self.hvac_mode,
                self.fan_mode,
                self.hvac_action,
                self.cool_target,
                self.heat_target,
            )
            # pylint: enable=line-too-long

    def parse_thermostat_mode_action(self, state) -> None:
        """Parse thermostat mode and action from the state."""

        # [Aux mode]
        #     Off
        #     operating_mode=current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #     Heat
        #     operating_mode=current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 100, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706456258}

        #     Cool
        #     operating_mode=current_operating_mode=cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706456358}

        #     Aux
        #     operating_mode=current_operating_mode=aux
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': 1, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 100, 'last': 'heat', 'last_start': 1706456438}

        # [Off]
        #     Off
        #     operating_mode=off, current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        # [Heat]
        #     Heating:
        #     operating_mode=heat, current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706461614}

        #     idle:
        #     operating_mode=heat, current_operating_mode=heat
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        # [Cool]
        #     Idle:
        #     operating_mode=off, current_operating_mode=off
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'cool', 'last_start': None}

        #     Cooling:
        #     operating_mode=cool, current_operating_mode=cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706461689}

        # [Auto]
        #     cooling:
        #     operating_mode=auto, current_operating_mode=auto_cool
        #     demand_status={'cool_stage': 1, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 100, 'cool': 100, 'aux': 0, 'last': 'cool', 'last_start': 1706462094}

        #     idle:
        #     operating_mode=auto, current_operating_mode=auto_heat
        #     demand_status={'cool_stage': None, 'heat_stage': None, 'aux_stage': None, 'heat': 0, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': None}

        #     heating
        #     operating_mode=auto, current_operating_mode=auto_heat
        #     demand_status={'cool_stage': None, 'heat_stage': 1, 'aux_stage': None, 'heat': 100, 'fan': 0, 'cool': 0, 'aux': 0, 'last': 'heat', 'last_start': 1706462635}

        # When thermostat is set to Off, operating_mode and current_operating_mode are both Off. Themostat should not be be demanding heating or cooling

        LOGGER.debug(
            "operating_mode=%s, demand_status=%s",
            state["operating_mode"],
            state["demand_status"],
        )

        if "operating_mode" in state:
            self.operating_mode = state["operating_mode"]
            self.hvac_mode = OPERATING_MODE_TO_HVAC_MODE.get(self.operating_mode)
        else:
            LOGGER.debug("operating_mode not found in data")

        if self.operating_mode == OperatingModes.OFF:
            self.effective_operating_mode = OperatingModes.OFF
            self.hvac_action = HVACAction.OFF
        elif "demand_status" in state:
            demand_status = state["demand_status"]
            self.last_action_heat = demand_status.get("last") == "heat"

            if demand_status.get("aux", 0) > 0:
                self.effective_operating_mode = OperatingModes.AUX
                self.hvac_action = HVACAction.HEATING  # Treat Aux as Heating
            elif demand_status.get("heat", 0) > 0:
                self.effective_operating_mode = OperatingModes.HEAT
                self.hvac_action = HVACAction.HEATING
            elif demand_status.get("cool", 0) > 0:
                self.effective_operating_mode = OperatingModes.COOL
                self.hvac_action = HVACAction.COOLING
            else:
                self.effective_operating_mode = None
                self.hvac_action = HVACAction.IDLE
        else:
            LOGGER.debug("demand_status not found in data")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_action == HVACAction.OFF:
            return None
        if self.hvac_action == HVACAction.HEATING:
            return self.heat_target
        if self.hvac_action == HVACAction.COOLING:
            return self.cool_target

        # HVACAction.IDLE
        return self.heat_target if self.last_action_heat else self.cool_target

    async def async_set_temp(self, value: int) -> None:
        """Set the target temperature."""

        if self.hvac_mode == HVACMode.HEAT:
            if self.heat_target == value:
                return
        elif self.hvac_mode == HVACMode.COOL:
            if self.cool_target == value:
                return

        # com.emerson.sensi.api.events.SetTemperatureEvent > set_temperature, toJson
        data = self.build_set_request_str(
            "temperature",
            {
                "target_temp": value,
                "mode": self.operating_mode.lower(),
                "scale": self._display_scale,
            },
        )
        await self.coordinator.async_send_event(data)

        if self.hvac_mode == HVACMode.HEAT:
            self.heat_target = value
        elif self.hvac_mode == HVACMode.COOL:
            self.cool_target = value

    async def async_set_fan_mode(self, mode: str) -> None:
        """Set the fan mode."""

        mode = mode.lower()
        if self.fan_mode == mode:
            return

        # com.emerson.sensi.api.events.SetFanModeEvent > set_fan_mode, toJson
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

        if (self.attributes[ATTR_CIRCULATING_FAN] == status) and (
            self.attributes[ATTR_CIRCULATING_FAN_DUTY_CYCLE] == duty_cycle
        ):
            return

        # com.emerson.sensi.api.events.SetCirculatingFanEvent > set_fan_mode
        data = self.build_set_request_str(
            "circulating_fan",
            {"value": {"enabled": status, "duty_cycle": duty_cycle}},
        )
        await self.coordinator.async_send_event(data)

        self.attributes[ATTR_CIRCULATING_FAN] = status
        self.attributes[ATTR_CIRCULATING_FAN_DUTY_CYCLE] = duty_cycle

    async def async_set_operating_mode(self, mode: OperatingModes) -> bool:
        """Update the operating and hvac mode.

        com.emerson.sensi.api.events.SetSystemModeEvent > "set_operating_mode".
        """

        if mode == self.operating_mode:
            return False

        data = self.build_set_request_str("operating_mode", {"value": mode})
        await self.coordinator.async_send_event(data)
        self.operating_mode = mode
        self.effective_operating_mode = mode

        self.hvac_mode = OPERATING_MODE_TO_HVAC_MODE.get(mode)
        return True

    async def async_enable_aux_mode(self) -> bool:
        """Set auxiliary heating mode."""
        if self.effective_operating_mode == OperatingModes.AUX:
            return False

        mode = OperatingModes.AUX
        data = self.build_set_request_str("operating_mode", {"value": mode})
        await self.coordinator.async_send_event(data)
        self.operating_mode = OperatingModes.HEAT
        self.effective_operating_mode = OperatingModes.AUX
        self.hvac_mode = HVACMode.HEAT
        return True

    def get_setting(self, key: Settings) -> bool | None:
        """Get value for a setting."""
        return self._properties.get(key)

    async def async_set_setting(self, key: Settings, value: bool | int) -> None:
        """Set value for a setting ."""

        if key not in Settings:
            raise ValueError(f"Unsupported setting: {key}")

        if value == self.get_setting(key):
            return

        if isinstance(value, bool):
            data = self.build_set_request_str(key, {"value": "on" if value else "off"})
        else:
            data = self.build_set_request_str(key, {"value": value})

        await self.coordinator.async_send_event(data)
        self._properties[key] = value

    async def async_set_min_temp(self, value: int) -> None:
        """Set the minimum thermostat temperature."""
        if self.min_temp == value:
            return

        await self.async_set_setting(Settings.COOL_MIN_TEMP, value)
        self.min_temp = value

    async def async_set_max_temp(self, value: int) -> None:
        """Set the maximum thermostat temperature."""
        if self.max_temp == value:
            return

        await self.async_set_setting(Settings.HEAT_MAX_TEMP, value)
        self.max_temp = value

    def build_set_request_str(self, key: str, payload: dict[str, str]) -> str:
        """Prepare the request string for setting data."""

        data = payload.copy()
        data["icd_id"] = self.identifier
        json_data = [f"set_{key}", data]
        return json.dumps(json_data)


class SensiUpdateCoordinator(DataUpdateCoordinator):
    """The Sensi data update coordinator."""

    _last_event_time_stamp: datetime | None = None

    def __init__(self, hass: HomeAssistant, config: AuthenticationConfig) -> None:
        """Initialize Sensi coordinator."""

        self._devices: dict[str, SensiDevice] = {}
        # self._login_retry = 0
        self._last_update_failed = False  # Used for debugging

        self._setup_headers(config)

        super().__init__(
            hass,
            LOGGER,
            name="SensiUpdateCoordinator",
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

    def _setup_headers(self, config: AuthenticationConfig):
        # self._access_token = config.access_token
        self._headers = {"Authorization": "bearer " + config.access_token}
        # self._expires_at = config.expires_at

    def get_devices(self) -> list[SensiDevice]:
        """Sensi devices."""
        return self._devices.values()

    def get_device(self, icd_id):
        """Return a specific Sensi device."""
        return self._devices.get(icd_id)

    def _parse_socket_response(self, msg: str, devices: dict[str, SensiDevice]) -> bool:
        """Parse the websocket device response."""
        if not msg:
            return False

        if msg.startswith("44"):
            # 44{"message":"jwt expired","code":"invalid_token","type":"UnauthorizedError"}
            raise AuthenticationError

        if not msg.startswith("42"):
            # Some other failure
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

        # Continue to use the current acces_tooken. We need a new refresh_tokken to get an access_token
        # if not await self._verify_authentication():
        #    return self._devices

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

                except (
                    asyncio.TimeoutError,
                    websockets.exceptions.WebSocketException,
                ) as exception:
                    done = True
                    self._last_update_failed = True
                    raise UpdateFailed(exception) from exception
                except AuthenticationError as exception:
                    raise ConfigEntryAuthFailed from exception

        return self._devices

    async def async_send_event(self, data: str) -> None:
        """Send a JSON request."""

        await self.async_send_event_priv(data)

    async def async_send_event_priv(self, data: str) -> None:
        """Send a JSON request."""

        self._last_event_time_stamp = None

        async with websockets.client.connect(
            WS_URL, extra_headers=self._headers
        ) as websocket:
            try:
                await websocket.send("421" + data)
                msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                self._last_event_time_stamp = datetime.now()
                LOGGER.debug("async_send_event response=%s", msg)
            except Exception as err:  # pylint: disable=broad-except
                LOGGER.warning("Sending event with %s failed", data)
                LOGGER.warning(str(err))

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
