"""Sensi Client for connecting to Sensi thermostats via socketio."""

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import asdict, dataclass
from types import TracebackType
from typing import Self

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
    BoolEventData,
    NumberEventData,
    SetCirculatingFanEvent,
    SetCirculatingFanEventValue,
    SetFanModeEvent,
    SetHumidityEvent,
    SetHumidityEventValue,
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
DISCONNECT_TIMEOUT = 10


@dataclass
class ActionResponse:
    """Response for an action.

    For a failure, error is the error code or message and data is None.
    For a success, error is None and the data can be empty.
    """

    error: str | None
    data: any


class SensiClient:
    """Sensi Client for connecting to Sensi thermostats via socketio."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AuthenticationConfig,
        connector: aiohttp.TCPConnector,
    ) -> None:
        """Initialize the Sensi Client."""

        self._did_token_expire_midway = False

        self._hass = hass
        self._config = config
        self._connector = connector

        self._event_queue = asyncio.Queue()
        self._futures: dict[tuple[str, str | None], list[asyncio.Future]] = {}
        self._emit_loop_task = None
        self._sio: socketio.AsyncClient = None
        self._connect_error_data = None
        self._devices: dict[str, SensiDevice] = {}

    async def __aenter__(self) -> Self:
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

        async def _wait_for_device_info() -> None:
            """Wait for info and capabilities getter events."""

            if not self._devices:
                return

            tasks = []
            task_icd_ids: dict[asyncio.Future, str] = {}
            for icd_id in self._devices:
                data = {"icd_id": icd_id}
                await self._send_event("get_info", data)
                await self._send_event("get_capabilities", data)

                info_future = await self._create_event_future("info", icd_id)
                capabilities_future = await self._create_event_future(
                    "capabilities", icd_id
                )
                tasks.extend([info_future, capabilities_future])
                task_icd_ids[info_future] = icd_id
                task_icd_ids[capabilities_future] = icd_id

            done, pending = await asyncio.wait(tasks, timeout=PREPARE_DEVICES_TIMEOUT)

            # Handle partial success, this can happen if a device is permanently offline (can't even be removed from the account)
            if pending:
                unresponsive = {task_icd_ids[t] for t in pending}
                for t in pending:
                    t.cancel()
                LOGGER.warning(
                    "Timed out waiting for info/capabilities from device(s) %s; continuing without them",
                    ", ".join(sorted(unresponsive)),
                )

            if not done:
                raise TimeoutError(
                    f"No devices responded within {PREPARE_DEVICES_TIMEOUT} seconds"
                )

        async def _wait_for_state_and_device_info() -> None:
            """Wait for the initial `state` event so that we can iterate and issue info and capabilities getter events."""

            await self._wait_for_event("state", None, PREPARE_DEVICES_TIMEOUT)
            LOGGER.info(f"{len(self._devices)} devices found")
            await _wait_for_device_info()

        try:
            await self._connect()
            await _wait_for_state_and_device_info()
        except SensiConnectionError as err:
            raise ConfigEntryNotReady from err
        except TimeoutError:
            LOGGER.warning(
                f"Unable to gather device information in {PREPARE_DEVICES_TIMEOUT} seconds, retrying"
            )
        else:
            return

        try:
            await _wait_for_device_info()
        except SensiConnectionError as err:
            raise ConfigEntryNotReady from err
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Unable to gather device information in {PREPARE_DEVICES_TIMEOUT} seconds"
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
        """Disconnect the client without raising an error.

        Bounded so a wedged socket.io teardown can never hang a coordinator
        update. With native reconnection disabled (see `_connect`) `wait()`
        returns promptly; the timeout is defense in depth.
        """
        if not self._sio or not self._sio.connected:
            return

        LOGGER.info("Disconnecting")

        with contextlib.suppress(Exception):
            await self._sio.disconnect()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._sio.wait(), DISCONNECT_TIMEOUT)

        self._sio = None

    async def async_update_devices(self) -> list[SensiDevice]:
        """Update the thermostat devices.

        This can raise SensiConnectionError.
        """

        # Disconnect and reconnect. There doesn't seem to be event for force state refresh.
        LOGGER.info("Updating devices - reconnecting and updating")
        await self._async_disconnect()
        await self._connect()

        # Refresh does no create new devices so let us just wait for device states. We don't
        # care the order in which state event is received. It can come before or after connected.
        async def _wait_for_device_states() -> None:
            tasks = [
                await self._create_event_future("state", icd_id)
                for icd_id in self._devices
            ]

            await asyncio.wait_for(asyncio.gather(*tasks), PREPARE_DEVICES_TIMEOUT)

        with contextlib.suppress(asyncio.exceptions.TimeoutError):
            await _wait_for_device_states()

    async def async_set_temperature(
        self, device: SensiDevice, mode: OperatingMode, value: int
    ) -> ActionResponse:
        """Set the target temperature. This updates the device on success."""

        state = device.state

        if state.operating_mode == OperatingMode.OFF:
            return ActionResponse(
                f"Cannot set {mode} temperature whern thermostat is OFF.",
                None,
            )

        request = SetTemperatureEvent(
            device.identifier,
            state.display_scale,
            mode.value,
            value,
        )
        action_response = await self._async_invoke_setter(
            "set_temperature", asdict(request)
        )

        if action_response.error:
            return action_response

        # {'current_temp': 70, 'mode': 'heat', 'target_temp': 75}
        response = SetTemperatureEventSuccess(**action_response.data)

        state.display_temp = response.current_temp

        # Changing cool/min temperature should not change the operating mode
        # In mobile app, one cannot set the temperatures if the device is OFF.
        if mode == OperatingMode.HEAT:
            state.current_heat_temp = response.target_temp
        if mode == OperatingMode.COOL:
            state.current_cool_temp = response.target_temp

        return ActionResponse(None, response)

    async def async_set_operating_mode(
        self, device: SensiDevice, value: OperatingMode
    ) -> ActionResponse:
        """Set new hvac operating mode. This updates the device on success."""

        request = SetOperatingModeEvent(
            device.identifier,
            value.value,
        )
        action_response = await self._async_invoke_setter(
            "set_operating_mode", asdict(request)
        )

        if action_response.error:
            return action_response

        response = action_response.data

        # We can receive a string instead of JSON
        if isinstance(response, str):
            if response == "accepted":
                device.state.operating_mode = value
                return action_response

            # Treat anything else other than "accepted" as error
            return ActionResponse(response, None)

        if response:
            try:
                parsed_response = SetOperatingModeEventSuccess(**response)
                device.state.operating_mode = parsed_response.mode
                return ActionResponse(None, None)
            except ValueError, TypeError:
                return ActionResponse(f"Failed to parse `{response}`", None)

        return ActionResponse("No response received", None)

    async def async_set_circulating_fan_mode(
        self, device: SensiDevice, enabled: bool, duty_cycle: int
    ) -> ActionResponse:
        """Set the circulating fan mode. This updates the device on success."""

        if not device.capabilities.circulating_fan.capable:
            raise HomeAssistantError(
                f"{self.identifier}: circulating fan mode was set but the device does not support it"
            )

        # "circulating_fan":{"capable":"yes","max_duty_cycle":100,"min_duty_cycle":10,"step":5}
        request = SetCirculatingFanEvent(
            device.identifier, SetCirculatingFanEventValue(enabled, duty_cycle)
        )
        action_response = await self._async_invoke_setter(
            SettingEventName.CIRCULATING_FAN.value, asdict(request)
        )

        if not action_response.error:
            device.state.circulating_fan.enabled = enabled
            device.state.circulating_fan.duty_cycle = duty_cycle

        return action_response

    async def async_set_fan_mode(
        self, device: SensiDevice, mode: str
    ) -> ActionResponse:
        """Set the fan mode. This updates the device on success."""

        request = SetFanModeEvent(device.identifier, mode)
        action_response = await self._async_invoke_setter(
            "set_fan_mode", asdict(request)
        )

        if not action_response.error:
            # Doesn't look like the mode can change at server end, no response was received.
            device.state.fan_mode = try_parse_enum(FanMode, mode)

        return action_response

    async def async_set_temperature_offset(
        self, device: SensiDevice, value: int
    ) -> ActionResponse:
        """Set the temperature offset. This updates the device on success."""

        # Limits are enforced in the entity description
        request = NumberEventData(device.identifier, value)
        response = await self._async_invoke_setter("set_temp_offset", asdict(request))

        if not response.error:
            device.state.temp_offset = value

        return response

    async def async_set_humidity_offset(
        self, device: SensiDevice, value: int
    ) -> ActionResponse:
        """Set the humidity offset. This updates the device on success."""

        # Limits are enforced in the entity description
        request = NumberEventData(device.identifier, value)
        response = await self._async_invoke_setter(
            "set_humidity_offset", asdict(request)
        )

        if not response.error:
            device.state.humidity_offset = value

        return response

    async def async_set_bool_setting(
        self, device: SensiDevice, event: SettingEventName, value: bool
    ) -> ActionResponse:
        """Set a generic bool setting. This updates the device on success."""

        request = BoolEventData(device.identifier, value)
        event_name = event.value
        action_response = await self._async_invoke_setter(event_name, asdict(request))

        if not action_response.error:
            attr_name = event_name[4:]
            setattr(device.state, attr_name, value)

        return action_response

    async def async_set_humidification(
        self, device: SensiDevice, enabled: bool, humidity: int
    ) -> ActionResponse:
        """Set the target humidity. This updates the device on success."""

        humidity = round_humidity(
            humidity,
            device.state.humidity_control.humidification.target_percent,
            device.capabilities.humidity_control.humidification.step,
        )

        request = SetHumidityEvent(
            device.identifier, SetHumidityEventValue(enabled, humidity)
        )
        action_response = await self._async_invoke_setter(
            "set_humidification", asdict(request)
        )

        if not action_response.error:
            device.state.humidity_control.humidification.enabled = enabled
            device.state.humidity_control.humidification.target_percent = humidity

        return action_response

    async def async_enable_humidification(
        self, device: SensiDevice, enabled: bool
    ) -> ActionResponse:
        """Update the humidification status. This updates the device on success."""

        # Use current target as the value
        return await self.async_set_humidification(
            device, enabled, device.state.humidity_control.humidification.target_percent
        )

    async def _async_invoke_setter(
        self, event: str, request_data: dict
    ) -> ActionResponse:
        """Emit event to update a setting."""

        future = self._hass.loop.create_future()

        def event_callback(*response_args: any) -> None:
            if future.cancelled():
                return

            with contextlib.suppress(asyncio.exceptions.InvalidStateError):
                if not response_args:
                    future.set_result((None, {}))
                    return

                if len(response_args) >= 2:
                    future.set_result((response_args[0], response_args[1]))
                    return

                response_payload = response_args[0]
                if response_payload is None:
                    future.set_result((None, {}))
                    return

                if isinstance(response_payload, dict) and "error" in response_payload:
                    future.set_result((response_payload, None))
                    return

                future.set_result((None, response_payload))

        await self._send_event(event, request_data, event_callback)

        with contextlib.suppress(asyncio.exceptions.TimeoutError):
            await asyncio.wait_for(future, SET_EVENT_TIMEOUT)

        # Treat this as failure
        if not future.done():
            return ActionResponse("Future not done", None)

        (response_error, response_data) = future.result()

        if response_error:
            return ActionResponse(
                get_error_description_from_event_callback(response_error), None
            )

        return ActionResponse(None, response_data or {})

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

    def _on_event(self, event: str, data: any) -> None:
        if event == "state":
            self._update_state(data)
        elif event == "capabilities":
            self._update_capabilities(data)
        elif event == "info":
            self._update_info(data)
        else:
            # Resolve future for all other events
            self._resolve_futures(event, None, None)

    def _resolve_futures(self, event: str, icd_id: str | None, data: any) -> None:
        """Resolve futures.

        icd_id is None for the initial `state` event.
        """
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
            # self._sio is briefly None while a reconnect refreshes the token,
            # so guard every access to avoid crashing this background task.
            if self._sio and self._sio.connected:
                try:
                    while item := self._event_queue.get_nowait():
                        if self._sio and self._sio.connected:
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
                LOGGER.debug(f"In event emit loop ({self._config.user_id}): {count}")

            count = count + 1

    async def _connect(self) -> None:
        """Make a connection and wait for `connected` event.

        This can raise SensiConnectionError, AuthenticationError.
        """

        # Create SocketIO client with reconnection limited to 1 attempt. Add engineio_logger=LOGGER for deeper debugging
        sio = self._sio = socketio.AsyncClient(logger=LOGGER, reconnection_attempts=1)

        @sio.event
        async def connect():
            self._ensure_emit_loop()
            self._on_event("connected", None)

        @sio.event
        async def connect_error(data):
            LOGGER.debug(f"Received connection error ({data})")
            self._connect_error_data = data

            # Only the first connection error has useful data i.e. jwt expired in it. The connect_error due to automatic retires
            # just has "Connection error" in it. So we only check for token expiry in the first connect_error.
            if is_token_expired(data):
                self._did_token_expire_midway = True

        @sio.event
        async def disconnect(reason) -> None:
            LOGGER.debug(f"Disconnected ({reason})")

            # Log samples

            # 1. Disconnect is recoverable

            # 2026-07-15 13:52:54.133 INFO (MainThread) [custom_components.sensi] Engine.IO connection dropped
            # 2026-07-15 13:52:54.134 DEBUG (MainThread) [custom_components.sensi] Disconnected (transport error)
            # 2026-07-15 13:52:54.134 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 1.03 seconds
            # 2026-07-15 13:52:55.292 INFO (MainThread) [custom_components.sensi] Engine.IO connection established
            # 2026-07-15 13:52:55.326 INFO (MainThread) [custom_components.sensi] Namespace / is connected
            # 2026-07-15 13:52:55.326 INFO (MainThread) [custom_components.sensi] Reconnection successful
            # 2026-07-15 13:52:55.342 INFO (MainThread) [custom_components.sensi] Received event "state" [/]
            # 2026-07-15 13:52:55.350 INFO (MainThread) [custom_components.sensi] Received event "state" [/]
            # 2026-07-15 13:52:55.351 DEBUG (MainThread) [custom_components.sensi] 36-6f-92-ff-fe-0c-0b-07 State updated to State(status=online, operating_mode=cool, display_temp=74.5°F, humidity=98%

            # 2. Disconnect itself doesn't have useful data, the useful reason is in connect_error.

            # 2026-07-15 17:18:10.721 DEBUG (MainThread) [custom_components.sensi] Disconnected (transport error)
            # 2026-07-15 17:18:10.721 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 0.99 seconds
            # 2026-07-15 17:18:11.851 DEBUG (MainThread) [custom_components.sensi] Received connection error (Connection error)
            # 2026-07-15 17:18:11.852 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 1.97 seconds
            # 2026-07-15 17:18:13.854 DEBUG (MainThread) [custom_components.sensi] Received connection error (Connection error)
            # 2026-07-15 17:18:13.854 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 4.37 seconds
            # 2026-07-15 17:18:14.030 DEBUG (MainThread) [custom_components.sensi] In event emit loop (<user_id>): 38060

            # 3. If token is identified expired during data update, then it is refreshed

            # 2026-07-15 23:15:02.172 INFO (MainThread) [custom_components.sensi] Updating devices - reconnecting and updating
            # 2026-07-15 23:15:02.172 INFO (MainThread) [custom_components.sensi] Disconnecting
            # 2026-07-15 23:15:02.173 INFO (MainThread) [custom_components.sensi] Engine.IO connection dropped
            # 2026-07-15 23:15:02.173 DEBUG (MainThread) [custom_components.sensi] client disconnect
            # 2026-07-15 23:15:03.364 INFO (MainThread) [custom_components.sensi] Engine.IO connection established
            # 2026-07-15 23:15:03.398 INFO (MainThread) [custom_components.sensi] Connection to namespace / was rejected
            # 2026-07-15 23:15:03.398 DEBUG (MainThread) [custom_components.sensi] Received connection error ({'message': 'jwt expired', 'data': {'message': 'jwt expired', 'code': 'invalid_token', 'type': 'UnauthorizedError'}})
            # 2026-07-15 23:15:03.399 INFO (MainThread) [custom_components.sensi] Engine.IO connection dropped
            # 2026-07-15 23:15:03.432 DEBUG (MainThread) [custom_components.sensi] Using supplied refresh_token <redacted>
            # 2026-07-15 23:15:03.432 DEBUG (MainThread) [custom_components.sensi] Getting access token using refresh_token=<redacted>
            # 2026-07-15 23:15:03.756 INFO (MainThread) [custom_components.sensi] Engine.IO connection established
            # 2026-07-15 23:15:03.790 INFO (MainThread) [custom_components.sensi] Namespace / is connected
            # 2026-07-15 23:15:03.790 DEBUG (MainThread) [custom_components.sensi] Creating future (state, 36-6f-92-ff-fe-0c-0b-07)
            # 2026-07-15 23:15:03.839 INFO (MainThread) [custom_components.sensi] Received event "state" [/]

            # But token expiry midway is not intercepted, the connection retires are being done internally in Engine.IO.
            # The automatic retries give a different reason "Connection error". Only the first reason has jwt_expired in it.

            # 2026-07-16 04:27:39.646 INFO (MainThread) [custom_components.sensi] Engine.IO connection dropped
            # 2026-07-16 04:27:39.646 DEBUG (MainThread) [custom_components.sensi] Disconnected (transport error)
            # 2026-07-16 04:27:39.646 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 1.35 seconds
            # 2026-07-16 04:27:41.122 INFO (MainThread) [custom_components.sensi] Engine.IO connection established
            # 2026-07-16 04:27:41.151 INFO (MainThread) [custom_components.sensi] Connection to namespace / was rejected
            # 2026-07-16 04:27:41.151 DEBUG (MainThread) [custom_components.sensi] Received connection error ({'message': 'jwt expired', 'data': {'message': 'jwt expired', 'code': 'invalid_token', 'type': 'UnauthorizedError'}})
            # 2026-07-16 04:27:41.152 INFO (MainThread) [custom_components.sensi] Engine.IO connection dropped
            # 2026-07-16 04:27:41.183 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 1.73 seconds
            # 2026-07-16 04:27:43.032 DEBUG (MainThread) [custom_components.sensi] Received connection error (Connection error)
            # 2026-07-16 04:27:43.033 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 4.18 seconds
            # 2026-07-16 04:27:47.239 DEBUG (MainThread) [custom_components.sensi] Received connection error (Connection error)
            # 2026-07-16 04:27:47.239 INFO (MainThread) [custom_components.sensi] Connection failed, new attempt in 5.26 seconds
            # 2026-07-16 04:27:47.679 DEBUG (MainThread) [custom_components.sensi] In event emit loop (<user_id>): 116000
            # 2026-07-16 04:27:51.173 INFO (MainThread) [custom_components.sensi] Updating devices - reconnecting and updating

        @sio.on("*")
        async def any_event(event, data):
            self._on_event(event, data)

        # raise SensiConnectionError("Fake error, could not connect")   # For testing

        try:
            # If data retreival failed due to token expiring midway or the token is expired/expiring, then refresh the access token before
            # trying to connect again. try_refresh_access_token can raise errors, doing within try/catch reset connection state in finally block.
            if self._did_token_expire_midway or self._config.is_expired:
                LOGGER.debug(
                    "Access token missing or expired; refreshing before connect"
                )
                await self.try_refresh_access_token()

            await self._connect_client()
        except TimeoutError as ex:
            raise SensiConnectionError("Timed out making the connection") from ex
        except ConnectionError as connect_ex:
            if not is_token_expired(self._connect_error_data):
                raise SensiConnectionError(
                    f"Connection failed but token was not expired. ConnectError={self._connect_error_data}"
                ) from connect_ex

            await self.try_refresh_access_token()

            # Try connecting again after refreshing tokens. Pass all exceptions.

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
        except Exception as err:
            raise SensiConnectionError("Failed to connect") from err
        finally:
            self._reset_connection_state()

    async def try_refresh_access_token(self) -> None:
        """Try refreshing the access token.

        This can raise SensiConnectionError, AuthenticationError.
        """
        try:
            self._config = await refresh_access_token(
                self._hass, self._config.refresh_token
            )
        except Exception as err:
            raise SensiConnectionError("Error refreshing tokens") from err

    async def _connect_client(self) -> None:
        """Make a connection.

        This can raise ConnectionError, TimeoutError.
        """

        self._reset_connection_state()

        query = "?capabilities=display_humidity,operating_mode_settings,fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,outdoor_stages,continuous_backlight,degrees_fc,display_time,keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,humidity_control,humidity_offset,humidity_offset_lower_bound,humidity_offset_upper_bound,temp_offset_lower_bound,temp_offset_upper_bound,lowest_heat_setpoint_ceiling,heat_setpoint_ceiling,highest_cool_setpoint_floor,cool_setpoint_floor"
        await self._sio.connect(
            SOCKET_URL + query,
            headers=self._config.headers,
            socketio_path="/thermostat",
            transports=["websocket"],
        )

    def _reset_connection_state(self):
        """Reset the connection state."""
        self._connect_error_data = None
        self._did_token_expire_midway = False

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

    def _update_state(self, data):
        """Handle state event from socketio."""
        if not data or len(data) == 0:
            return

        futures_to_resolve = []

        for item in data:
            icd_id = extract_icd_id(item)
            if icd_id:
                have_state = False

                # The first state event received on connect usually only contains registration and capabilities.
                # The second state event received on connect contains registration, capabilities and state.
                # Only resolve `state` futures if we received state data.

                if icd_id not in self._devices:
                    (have_state, device) = SensiDevice.create(item)
                    self._devices[icd_id] = device
                else:
                    have_state = self._devices[icd_id].update_state(item)

                if have_state:
                    futures_to_resolve.append((icd_id, item))

        # First resolve the initial `state` event future and then per-device futures.
        self._resolve_futures("state", None, None)

        for item in futures_to_resolve:
            self._resolve_futures("state", item[0], item[1])

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


def round_humidity(humidity: int, current_humidity: int, step: int) -> int:
    """Return the rounded target humidity value."""

    # e.g. 12 -> 10, 14 -> 15, 17 -> 15, 20 -> 20
    rounded_to_nearest_5 = step * round(humidity / step)

    if humidity > current_humidity:
        if rounded_to_nearest_5 == current_humidity:
            humidity = current_humidity + step
        else:
            humidity = rounded_to_nearest_5
    elif humidity < current_humidity:
        if rounded_to_nearest_5 == current_humidity:
            humidity = current_humidity - step
        else:
            humidity = rounded_to_nearest_5

    return humidity


@dataclass
class EventInfo:
    """Data for emitting an event."""

    name: str
    data: any
    callback: Callable[[any, any], None]


def raise_if_error(response: ActionResponse, property: str, value: any) -> None:
    """Raise HomeAssistantError if error is defined.

    The exception is raised with the message `Unable to set {property} to {value}. {error}`.
    """

    # Potential error codes returned from Sensi end point: ThermostatOffline, OutOfRange, Bad Request

    if response.error:
        raise HomeAssistantError(
            f"Unable to set {property} to {value}. {response.error}"
        )
