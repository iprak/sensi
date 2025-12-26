"""Sensi Client for connecting to Sensi thermostats via socketio."""

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import asdict, dataclass
from types import TracebackType

import aiohttp
import socketio
from socketio.exceptions import ConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.enum import try_parse_enum

from .auth import SensiConnectionError, refresh_access_token
from .const import LOGGER
from .data import AuthenticationConfig, FanMode, OperatingMode, SensiDevice
from .event import (
    SetCirculatingFanEventInfo,
    SetCirculatingFanEventValue,
    SetFanModeEventInfo,
    SetFanModeEventSuccessInfo,
    SetOperatingModeEventInfo,
    SetOperatingModeSuccessInfo,
    SetTemperatureEventInfo,
    SetTemperatureSuccessInfo,
    SettingEventName,
)

SOCKET_URL = "https://rt.sensiapi.io"


class SensiClient:
    """Sensi Client for connecting to Sensi thermostats via socketio."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AuthenticationConfig,
        connector: aiohttp.TCPConnector,
    ) -> None:
        """Initialize the Sensi Client."""

        self._hass = hass
        self._config = config
        self._connector = connector

        self._event_queue = asyncio.Queue()
        self._futures: dict[tuple[str, str], list[asyncio.Future]] = {}
        self._emit_loop_task = None
        self._sio: socketio.AsyncClient = None
        self._connect_error_data = None
        self._devices: dict[str, SensiDevice] = {}

    async def __aenter__(self) -> "SensiClient":
        """Enter context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Leave context manager and disconnect the client."""
        await self._async_disconnect()
        return False

    def get_devices(self) -> list[SensiDevice]:
        """Get the list of thermostat devices."""
        return list(self._devices.values())

    async def wait_for_devices(self) -> None:
        """Wait for devices to be ready.

        This can raise TimeoutError, SensiConnectionError, AuthenticationError.
        """

        async def _wait_for_devices() -> None:
            await self._connect()
            await self._wait_for_event("state", "", 10)

            await self._load_devices_info()
            await self._load_devices_capabilities()

        await self._hass.async_create_task(_wait_for_devices())

    async def async_update_devices(self) -> list[SensiDevice]:
        """Update the thermostat devices."""

        await self._async_disconnect()

        async def _wait_for_devices() -> None:
            await self._connect()
            await self._wait_for_event("state", "")

        await self._hass.async_create_task(_wait_for_devices())

    async def async_set_temperature(self, device: SensiDevice, value: int) -> bool:
        """Set the target temperature.

        This raises HomeAssistantError for failures.
        """

        request = SetTemperatureEventInfo(
            device.identifier,
            device.state.display_scale,
            device.state.operating_mode.value,
            value,
        )
        response = await self._async_invoke_setter("set_temperature", asdict(request))

        if not response:
            return False

        # {'current_temp': 70, 'mode': 'heat', 'target_temp': 75}
        response = SetTemperatureSuccessInfo(**response)

        state = device.state
        state.display_temp = response.current_temp
        state.operating_mode = try_parse_enum(OperatingMode, response.mode)

        if state.operating_mode == OperatingMode.HEAT:
            state.current_heat_temp = response.target_temp
        if state.operating_mode == OperatingMode.COOL:
            state.current_cool_temp = response.target_temp

        print("async_set_temperature done")
        return True

    async def async_set_operating_mode(
        self, device: SensiDevice, value: OperatingMode
    ) -> bool:
        """Set new hvac operating mode.

        This raises HomeAssistantError for failures.
        """

        request = SetOperatingModeEventInfo(
            device.identifier,
            value.value,
        )
        response = await self._async_invoke_setter(
            "set_operating_mode", asdict(request)
        )

        if not response:
            return False

        # We can receive a string instead of JSON
        if isinstance(response, str):
            if response == "accepted":
                device.state.operating_mode = value
        else:
            response = SetOperatingModeSuccessInfo(**response)
            device.state.operating_mode = response.mode

        print("async_set_operating_mode done")
        return True

    async def async_set_circulating_fan_mode(
        self, device: SensiDevice, enabled: bool, duty_cycle: int
    ) -> bool:
        """Set the circulating fan mode."""

        if not device.capabilities.circulating_fan.capable:
            raise HomeAssistantError(
                f"{self.identifier}: circulating fan mode was set but the device does not support it"
            )

        request = SetCirculatingFanEventInfo(
            device.identifier, SetCirculatingFanEventValue(enabled, duty_cycle)
        )
        response = await self._async_invoke_setter(
            "set_circulating_fan", asdict(request)
        )

        if not response:
            return False

        return True

    async def async_set_fan_mode(self, device: SensiDevice, mode: str) -> bool:
        """Set the fan mode."""

        request = SetFanModeEventInfo(device.identifier, mode)
        response = await self._async_invoke_setter("set_fan_mode", asdict(request))

        if not response:
            return False

        # We can receive a string instead of JSON
        if isinstance(response, str):
            if response == "accepted":
                device.state.fan_mode = try_parse_enum(FanMode, mode)
        else:
            response = SetFanModeEventSuccessInfo(**response)
            device.state.fan_mode = try_parse_enum(FanMode, response.mode)

        return True

    async def async_set_temperature_limits(
        self, device: SensiDevice, min_temp: bool, value: int
    ) -> bool:
        """Set the minimum thermostat temperature."""

        request = {
            "scale": device.state.display_scale,
            "value": value,
            "icd_id": device.identifier,
        }
        response = await self._async_invoke_setter(
            SettingEventName.COOL_MIN_TEMP
            if min_temp
            else SettingEventName.HEAT_MAX_TEMP,
            request,
        )

        if not response:
            return False

        if isinstance(response, str):
            if response == "accepted":
                device.state.cool_min_temp = value
                return True

        return False

    async def _async_invoke_setter(
        self, event: str, request_data: dict
    ) -> dict | str | None:
        """Set new hvac operating mode.

        This raises HomeAssistantError for failures.
        """

        future = self._hass.loop.create_future()

        def event_callback(error: dict, data: dict | None = None) -> None:
            future.set_result((error, data))

        await self._send_event(event, request_data, event_callback)
        await asyncio.wait_for(future, 5)

        if not future.done():
            return None

        (response_error, response_data) = future.result()

        if response_error:
            raise HomeAssistantError(
                f"Unable to set operating_mode. {get_error_description_from_event_callback(response_error)}"
            )

        return response_data

    async def _load_devices_info(self) -> None:
        """Load info about the thermostat devices."""
        for icd_id in self._devices:
            await self._send_event("get_info", {"icd_id": icd_id})
            await self._wait_for_event("info", icd_id)

    async def _load_devices_capabilities(self) -> None:
        """Load capabilities of the thermostat devices."""
        for icd_id in self._devices:
            await self._send_event("get_capabilities", {"icd_id": icd_id})
            await self._wait_for_event("capabilities", icd_id)

    async def _wait_for_event(self, event: str, icd_id: str, timeout: int = 5) -> None:
        """Wait for an event response."""

        print(f"Creating future ({event}, {icd_id})")
        future_key = (event, icd_id)

        if future_key in self._futures:
            futures = self._futures.get(future_key)
        else:
            futures = []
            self._futures[future_key] = futures

        future = self._hass.loop.create_future()
        futures.append(future)

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.exceptions.TimeoutError:
            LOGGER.error(f"Timeout waiting for event '{event}' on device {icd_id}.")

    async def _on_event(self, event: str, data):
        if event == "state":
            await self._update_state(data)
        elif event == "capabilities":
            self._update_capabilities(data)
        elif event == "info":
            self._update_info(data)

    def _resolve_futures(self, event: str, icd_id: str, data: any) -> None:
        print(f"Resolving future ({event},{icd_id})")
        future_key = (event, icd_id)
        pending_futures = self._futures.pop(future_key, [])

        with contextlib.suppress(asyncio.exceptions.InvalidStateError):
            for future in pending_futures:
                future.set_result(data)

    async def _send_event(
        self, name: str, data: dict, callback: Callable[[any, any], None] | None = None
    ) -> None:
        print(f"Queuing event {name}")
        await self._event_queue.put(EventInfo(name, data, callback))

    async def _emit_loop(self):
        """Emit queued events."""
        item: EventInfo

        count = 1

        while True:
            try:
                while item := self._event_queue.get_nowait():
                    # print(f"Emitting event {item.name}")
                    if self._sio.connected:
                        await self._sio.emit(item.name, item.data, None, item.callback)
                    else:
                        print(
                            f"Emitting event {item.name} failed .. not connected put it back on queue"
                        )
                        self._event_queue.put(item)
                        break
            except asyncio.QueueEmpty:
                pass
            except TypeError:
                LOGGER.exception("Unable to emit event")

            await asyncio.sleep(0.5)
            print(f"In event emit loop {count}")
            count = count + 1

    async def _connect(self) -> None:
        """Make a connection.

        This can raise TimeoutError, SensiConnectionError.
        """

        sio = self._sio = socketio.AsyncClient(logger=LOGGER)

        @sio.event
        async def connect():
            self._on_connected()

        @sio.event
        async def connect_error(data):
            self._connect_error_data = data

        # @sio.event
        # async def disconnect(reason) -> None:
        #     print("I'm disconnected! reason:", reason)

        @sio.on("*")
        async def any_event(event, data):
            await self._on_event(event, data)

        # raise SensiConnectionError("Fake error, could not connect")   # For testing

        try:
            self._connect_error_data = None
            await self._connect_client()
        except ConnectionError as connect_ex:
            if not is_token_expired(self._connect_error_data):
                raise SensiConnectionError(
                    f"Connection failed but token was not expired. {self._connect_error_data}"
                ) from connect_ex

            try:
                self._config = await refresh_access_token(
                    self._hass, self._config.refresh_token
                )
            except Exception as refresh_ex:
                raise SensiConnectionError("Error refreshing tokens") from refresh_ex

            # Try connecting again after refreshing tokens. Pass all exceptions.
            self._connect_error_data = None

            try:
                await self._connect_client()
            except ConnectionError as connect_ex2:
                raise SensiConnectionError(
                    "Second connection attempt failed as well"
                ) from connect_ex2

    async def _connect_client(self) -> None:
        """Make a connection.

        This can raise ConnectionError, TimeoutError.
        """

        query = "capabilities=display_humidity,operating_mode_settings,fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,outdoor_stages,continuous_backlight,degrees_fc,display_time,keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,humidity_control,humidity_offset,humidity_offset_lower_bound,humidity_offset_upper_bound,temp_offset_lower_bound,temp_offset_upper_bound,lowest_heat_setpoint_ceiling,heat_setpoint_ceiling,highest_cool_setpoint_floor,cool_setpoint_floor"
        await self._sio.connect(
            SOCKET_URL + "?" + query,
            headers=self._config.headers,
            socketio_path="/thermostat",
            transports=["websocket"],
        )

    def _on_connected(self):
        if not self._emit_loop_task:
            self._emit_loop_task = asyncio.ensure_future(self._emit_loop())

    async def _async_disconnect(self) -> None:
        """Disconnect the client."""
        if self._sio:
            await self._sio.disconnect()
            await self._sio.wait()
            self._sio = None

    async def _update_state(self, data):
        """Handle state event from socketio."""
        if not data or len(data) == 0:
            return

        for item in data:
            # print(item)
            icd_id = extract_icd_id(item)
            if icd_id:
                if icd_id not in self._devices:
                    self._devices[icd_id] = SensiDevice(item)
                else:
                    self._devices[icd_id].update_state(item)

                # We don't have the icd_id when creating devices
                self._resolve_futures("state", "", item)
                self._resolve_futures("state", icd_id, item)

    def _update_info(self, data):
        if data:
            icd_id = extract_icd_id(data)
            if icd_id:
                if icd_id in self._devices:
                    self._devices[icd_id].update_info(data)

                self._resolve_futures("info", icd_id, data)

    def _update_capabilities(self, data):
        if data:
            icd_id = extract_icd_id(data)
            if icd_id:
                if icd_id in self._devices:
                    self._devices[icd_id].update_capabilities(data)

                self._resolve_futures("capabilities", icd_id, data)


def get_error_description_from_event_callback(error: dict) -> str:
    """Get error description from the event response error."""
    if not error:
        return ""

    # {'error': {'description': 'InvalidScale'}, 'icd_id': '36-6f-92-ff-fe-02-24-b7'}
    # {'error': {'description': 'Bad Request'}, 'icd_id': '36-6f-92-ff-fe-02-24-b7'}
    # {'error': {'description': 'Forbidden'}}
    return error.get("error", {}).get("description", "")


def is_token_expired(error_details):
    """Determine if the error details indicate an expired token."""
    if isinstance(error_details, dict):
        return error_details and error_details.get("message") == "jwt expired"
    return False


def extract_icd_id(data: dict) -> str:
    """Return the thermostat ICD ID."""
    return data.get("icd_id", "") if data else ""


@dataclass
class EventInfo:
    """Data for emitting an event."""

    name: str
    data: any
    callback: Callable[[any, any], None]
