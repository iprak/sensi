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
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.util.enum import try_parse_enum

from .auth import SensiConnectionError, refresh_access_token
from .const import LOGGER, SENSI_DOMAIN
from .data import AuthenticationConfig, FanMode, OperatingMode, SensiDevice
from .event import (
    SetBoolSettingEvent,
    SetCirculatingFanEvent,
    SetCirculatingFanEventValue,
    SetFanModeEvent,
    SetOperatingModeEvent,
    SetOperatingModeEventSuccess,
    SetTemperatureEvent,
    SetTemperatureEventSuccess,
    SettingEventName,
)

SOCKET_URL = "https://rt.sensiapi.io"
PREPARE_DEVICES_TIMEOUT = 20
SET_EVENT_TIMEOUT = 5
EMIT_LOOP_DELAY = 0.5
EMIT_LOOP_DELAY_WHEN_DISCONNECTED = 1


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

        This can raise ConfigEntryNotReady, AuthenticationError.
        """

        async def _wait_for_devices() -> None:
            # Wait for the generic `state` event.
            await self._wait_for_event("state", None, PREPARE_DEVICES_TIMEOUT)
            LOGGER.info(f"{len(self._devices)} devices found")

            tasks = []
            for icd_id in self._devices:
                data = {"icd_id": icd_id}
                await self._send_event("get_info", data)
                await self._send_event("get_capabilities", data)

                tasks.append(await self._create_event_future("info", icd_id))
                tasks.append(await self._create_event_future("capabilities", icd_id))

            await asyncio.wait_for(asyncio.gather(*tasks), PREPARE_DEVICES_TIMEOUT)

        try:
            await self._connect()
            await _wait_for_devices()
        except SensiConnectionError as err:
            raise ConfigEntryNotReady from err
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Initialization timed out after {PREPARE_DEVICES_TIMEOUT} seconds"
            ) from err

    async def stop(self) -> None:
        """Disconnect and stop the client."""
        await self._async_disconnect()

        if self._emit_loop_task:
            self._emit_loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._emit_loop_task

            self._emit_loop_task = None

    async def _async_disconnect(self) -> None:
        """Disconnect the client."""
        if self._sio:
            await self._sio.disconnect()
            await self._sio.wait()
            self._sio = None

    async def async_update_devices(self) -> list[SensiDevice]:
        """Update the thermostat devices.

        This can raise SensiConnectionError.
        """

        # Disconnect and reconnect. There doesn't seem to be event for force state refresh.
        await self._async_disconnect()
        await self._connect()

        # Refresh does no create new devices so let us just want for device states
        async def _wait_for_device_states() -> None:
            tasks = [
                await self._create_event_future("state", icd_id)
                for icd_id in self._devices
            ]

            await asyncio.wait_for(asyncio.gather(*tasks), PREPARE_DEVICES_TIMEOUT)

        with contextlib.suppress(asyncio.exceptions.TimeoutError):
            await _wait_for_device_states()

    async def async_set_temperature(
        self, device: SensiDevice, value: int
    ) -> tuple[any, any]:
        """Set the target temperature. This updates the device on success.

        Returns a tuple representing error and response.
        """

        request = SetTemperatureEvent(
            device.identifier,
            device.state.display_scale,
            device.state.operating_mode.value,
            value,
        )
        (error, response) = await self._async_invoke_setter(
            "set_temperature", asdict(request)
        )

        if error:
            return (error, response)

        # {'current_temp': 70, 'mode': 'heat', 'target_temp': 75}
        response = SetTemperatureEventSuccess(**response)

        state = device.state
        state.display_temp = response.current_temp
        state.operating_mode = try_parse_enum(OperatingMode, response.mode)

        if state.operating_mode == OperatingMode.HEAT:
            state.current_heat_temp = response.target_temp
        if state.operating_mode == OperatingMode.COOL:
            state.current_cool_temp = response.target_temp

        return (None, response)

    async def async_set_operating_mode(
        self, device: SensiDevice, value: OperatingMode
    ) -> tuple[any, any]:
        """Set new hvac operating mode. This updates the device on success.

        Returns a tuple representing error and response.
        """

        request = SetOperatingModeEvent(
            device.identifier,
            value.value,
        )
        (error, response) = await self._async_invoke_setter(
            "set_operating_mode", asdict(request)
        )

        if error:
            return (error, response)

        # We can receive a string instead of JSON
        if isinstance(response, str):
            if response == "accepted":
                device.state.operating_mode = value
        else:
            response = SetOperatingModeEventSuccess(**response)
            device.state.operating_mode = response.mode

        return (None, response)

    async def async_set_circulating_fan_mode(
        self, device: SensiDevice, enabled: bool, duty_cycle: int
    ) -> tuple[any, any]:
        """Set the circulating fan mode. This updates the device on success.

        Returns a tuple representing error and response.
        """

        if not device.capabilities.circulating_fan.capable:
            raise HomeAssistantError(
                f"{self.identifier}: circulating fan mode was set but the device does not support it"
            )

        request = SetCirculatingFanEvent(
            device.identifier, SetCirculatingFanEventValue(enabled, duty_cycle)
        )
        (error, response) = await self._async_invoke_setter(
            SettingEventName.CIRCULATING_FAN, asdict(request)
        )

        if error:
            return (error, response)

        device.state.circulating_fan.enabled = enabled
        device.state.circulating_fan.duty_cycle = duty_cycle
        return (None, response)

    async def async_set_fan_mode(
        self, device: SensiDevice, mode: str
    ) -> tuple[any, any]:
        """Set the fan mode. This updates the device on success.

        Returns a tuple representing error and response.
        """

        request = SetFanModeEvent(device.identifier, mode)
        (error, response) = await self._async_invoke_setter(
            "set_fan_mode", asdict(request)
        )

        if error:
            return (error, response)

        # Doesn't look like the mode can change at server end, no response was received.
        device.state.fan_mode = try_parse_enum(FanMode, mode)
        return (None, response)

    async def async_set_temperature_limits(
        self, device: SensiDevice, min_temp: bool, value: int
    ) -> tuple[any, any]:
        """Set the minimum/maximum thermostat temperature limits. This updates the device on success.

        Returns a tuple representing error and response.
        """

        request = {
            "scale": device.state.display_scale,
            "value": value,
            "icd_id": device.identifier,
        }
        (error, response) = await self._async_invoke_setter(
            SettingEventName.COOL_MIN_TEMP
            if min_temp
            else SettingEventName.HEAT_MAX_TEMP,
            request,
        )

        if error:
            return (error, response)

        if isinstance(response, str):
            if response == "accepted":
                if min_temp:
                    device.state.cool_min_temp = value
                else:
                    device.state.heat_max_temp = value

                return True

        return (None, response)

    async def async_set_bool_setting(
        self, device: SensiDevice, event: SettingEventName, value: bool
    ) -> tuple[any, any]:
        """Set a generic bool setting. This updates the device on success.

        Returns a tuple representing error and response.
        """

        request = SetBoolSettingEvent(device.identifier, value)
        event_name = event.value
        (error, response) = await self._async_invoke_setter(event_name, asdict(request))

        if error:
            return (error, response)

        attr_name = event_name[4:]
        setattr(device.state, attr_name, value)

        return (None, response)

    async def _async_invoke_setter(
        self, event: str, request_data: dict
    ) -> tuple[any, any]:
        """Emit event to update a setting.

        Returns a tuple representing error and response.
        """

        future = self._hass.loop.create_future()

        def event_callback(error: dict, data: dict | None = None) -> None:
            future.set_result((error, data))

        await self._send_event(event, request_data, event_callback)

        with contextlib.suppress(asyncio.exceptions.TimeoutError):
            await asyncio.wait_for(future, SET_EVENT_TIMEOUT)

        if not future.done():
            return None

        (response_error, response_data) = future.result()

        if response_error:
            return (get_error_description_from_event_callback(response_error), None)

        return (None, response_data or {})

    async def _wait_for_event(
        self, event: str, icd_id: str | None, timeout: int = 5
    ) -> None:
        """Wait for an event response."""

        future = await self._create_event_future(event, icd_id)

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.exceptions.TimeoutError:
            LOGGER.error(f"Timed out waiting for event '{event}' on device {icd_id}")

    async def _create_event_future(
        self, event: str, icd_id: str | None
    ) -> asyncio.Future:
        """Create an event future."""

        LOGGER.debug(f"Creating future ({event}, {icd_id})")
        future_key = (event, icd_id)
        futures = self._futures.get(future_key)

        if not futures:
            futures = []
            self._futures[future_key] = futures

        future = self._hass.loop.create_future()
        futures.append(future)

        return future

    async def _on_event(self, event: str, data: any) -> None:
        if event == "state":
            await self._update_state(data)
        elif event == "capabilities":
            self._update_capabilities(data)
        elif event == "info":
            self._update_info(data)
        else:
            # Resolve future for all other events
            self._resolve_futures(event, "", None)

    def _resolve_futures(self, event: str, icd_id: str, data: any) -> None:
        future_key = (event, icd_id)
        pending_futures = self._futures.pop(
            future_key, []
        )  # KeyError is raised if no entry is found and there is no default

        count = len(pending_futures)
        if count:
            LOGGER.debug(f"Resolving {count} futures for ({event}, {icd_id})")

            with contextlib.suppress(asyncio.exceptions.InvalidStateError):
                for future in pending_futures:
                    future.set_result(data)

    async def _send_event(
        self, name: str, data: dict, callback: Callable[[any, any], None] | None = None
    ) -> None:
        LOGGER.debug(f"Queuing event {name}")
        await self._event_queue.put(EventInfo(name, data, callback))

    async def _emit_loop(self):
        """Emit queued events."""
        item: EventInfo

        count = 0

        while True:
            if self._sio.connected:
                try:
                    while item := self._event_queue.get_nowait():
                        if self._sio.connected:
                            await self._sio.emit(
                                item.name, item.data, None, item.callback
                            )
                        else:
                            LOGGER.info(
                                f"Not connected. Putting {item.name} back on queue and quitting"
                            )
                            self._event_queue.put_nowait(item)
                            break
                except asyncio.QueueEmpty:
                    pass
                except TypeError:
                    LOGGER.exception("Unable to emit event")

                await asyncio.sleep(EMIT_LOOP_DELAY)
            else:
                await asyncio.sleep(EMIT_LOOP_DELAY_WHEN_DISCONNECTED)

            # Log approximately every 10 seconds based on EMIT_LOOP_DELAY
            if (count % 20) == 0:
                LOGGER.debug(f"In event emit loop ({self._config.user_id}): {count} ")

            count = count + 1

    async def _connect(self) -> None:
        """Make a connection and wait for `connected` event.

        This can raise SensiConnectionError.
        """

        sio = self._sio = socketio.AsyncClient(logger=LOGGER)

        @sio.event
        async def connect():
            self._ensure_emit_loop()
            await self._on_event("connected", None)

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
        except TimeoutError as ex:
            raise SensiConnectionError("Timed out making the connection") from ex
        except ConnectionError as connect_ex:
            if not is_token_expired(self._connect_error_data):
                raise SensiConnectionError(
                    f"Connection failed but token was not expired. ConnectError={self._connect_error_data}"
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
            except TimeoutError as ex:
                raise SensiConnectionError(
                    "Timed out making the connection after token refresh"
                ) from ex
            except ConnectionError as connect_ex2:
                raise SensiConnectionError(
                    "Connection attempt after token refresh failed"
                ) from connect_ex2
        except Exception as e:
            raise SensiConnectionError from e

    async def _connect_client(self) -> None:
        """Make a connection.

        This can raise ConnectionError, TimeoutError.
        """

        query = "?capabilities=display_humidity,operating_mode_settings,fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,outdoor_stages,continuous_backlight,degrees_fc,display_time,keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,humidity_control,humidity_offset,humidity_offset_lower_bound,humidity_offset_upper_bound,temp_offset_lower_bound,temp_offset_upper_bound,lowest_heat_setpoint_ceiling,heat_setpoint_ceiling,highest_cool_setpoint_floor,cool_setpoint_floor"
        await self._sio.connect(
            SOCKET_URL + query,
            headers=self._config.headers,
            socketio_path="/thermostat",
            transports=["websocket"],
        )

    def _ensure_emit_loop(self):
        if self._emit_loop_task and not self._emit_loop_task.done():
            return

        LOGGER.debug(
            f"Creating background task for the event emit loop ({self._config.user_id})"
        )
        self._emit_loop_task = self._hass.async_create_background_task(
            self._emit_loop(),
            name=f"{SENSI_DOMAIN}._emit_loop.{self._config.user_id}",
        )

    async def _update_state(self, data):
        """Handle state event from socketio."""
        if not data or len(data) == 0:
            return

        # We don't have the icd_id when creating devices
        self._resolve_futures("state", "", None)

        for item in data:
            icd_id = extract_icd_id(item)
            if icd_id:
                if icd_id not in self._devices:
                    self._devices[icd_id] = SensiDevice(item)
                else:
                    self._devices[icd_id].update_state(item)

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
    """Get the thermostat ICD ID."""
    return data.get("icd_id", "") if data else ""


@dataclass
class EventInfo:
    """Data for emitting an event."""

    name: str
    data: any
    callback: Callable[[any, any], None]
