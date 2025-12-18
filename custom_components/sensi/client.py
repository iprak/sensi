"""Sensi Client for connecting to Sensi thermostats via socketio."""

import asyncio
from types import TracebackType

import socketio

from homeassistant.core import HomeAssistant

from .auth import refresh_access_token
from .data import Thermostat, extract_icd_id

SOCKET_URL = "https://rt.sensiapi.io"


class SensiClient:
    """Sensi Client for connecting to Sensi thermostats via socketio."""

    _thermostats: dict[str, Thermostat] = None
    _event_received: list[str] = None
    _socket_closed: asyncio.Task | None = None
    _wants_to_close = False
    _connect_error_data = None

    def __init__(
        self, hass: HomeAssistant, access_token: str, refresh_token: str
    ) -> None:
        """Initialize the Sensi Client."""
        self._hass = hass
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._thermostats = {}

        self._setup_headers()
        event_loop = asyncio.get_event_loop()
        self._socket_closed = event_loop.create_task(self._socket_loop())
        print("SensiClient initialized")

    def _setup_headers(self):
        self._headers = {"Authorization": "bearer " + self._access_token}

    async def close(self) -> None:
        """Close the Sensi Client."""
        if self._socket_closed:
            self._wants_to_close = True
            await self._socket_closed
            self._socket_closed = None

    def get_thermostats(self) -> list[Thermostat]:
        """Get the list of thermostats."""
        #if self._socket_closed:
        #    await self._socket_closed
        return self._thermostats.values

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
        await self.close()
        return False

    async def _socket_loop(self) -> None:
        # sio = socketio.AsyncClient(logger=True, engineio_logger=True)
        sio = socketio.AsyncClient(logger=False)
        self._connect_error_data = None

        @sio.event
        async def connect():
            print("Connected to server")

        @sio.event
        async def connect_error(data):
            self._connect_error_data = data
            print(f"The connection failed! {data}")

        @sio.event
        async def disconnect(reason) -> None:
            print("I'm disconnected! reason:", reason)

        @sio.on("*")
        async def any_event(event, data):
            print(f"on_event ({event})")

            if event == "state":
                self.on_state(data)

        query = "capabilities=display_humidity,operating_mode_settings,fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,outdoor_stages,continuous_backlight,degrees_fc,display_time,keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,humidity_control,humidity_offset,humidity_offset_lower_bound,humidity_offset_upper_bound,temp_offset_lower_bound,temp_offset_upper_bound,lowest_heat_setpoint_ceiling,heat_setpoint_ceiling,highest_cool_setpoint_floor,cool_setpoint_floor"

        try:
            self._connect_error_data = None
            await sio.connect(
                SOCKET_URL + "?" + query,
                headers=self._headers,
                socketio_path="/thermostat",
                transports=["websocket"],
            )
        except Exception as e:
            print("Connection exception:", e)

            if is_token_expired(self._connect_error_data):
                try:
                    result = await refresh_access_token(self.hass, self._refresh_token)

                    self._access_token = result.access_token
                    self._refresh_token = result.refresh_token
                    self._setup_headers()

                    self._connect_error_data = None
                    await sio.connect(
                        SOCKET_URL + "?" + query,
                        headers=self._headers,
                        socketio_path="/thermostat",
                        transports=["websocket"],
                    )
                except Exception as e2:
                    print("Connection exception:", e2)

        if sio.connected:
            while not self._wants_to_close:
                print("Waiting _wants_to_close")
                await sio.sleep(1)

            print("Disconnecting from server")
            await sio.disconnect()
            await sio.wait()

    def on_state(self, data):
        """Handle state event from socketio."""
        if not data or len(data) == 0:
            return

        for item in data:
            # print(item)
            icd_id = extract_icd_id(item)
            if icd_id:
                if icd_id not in self._thermostats:
                    self._thermostats[icd_id] = Thermostat(item)
                else:
                    self._thermostats[icd_id].update_state(item)


def is_token_expired(error_details):
    """Determine if the error details indicate an expired token."""
    if isinstance(error_details, dict):
        return error_details and error_details.get("message") == "jwt expired"
    return False
