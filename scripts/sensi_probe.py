#!/usr/bin/env python3
"""Probe Sensi APIs with a refresh token.

This script is intentionally standalone so it can run without importing
Home Assistant modules from the integration.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
import sys
from typing import Any
from urllib import error, parse, request


OAUTH_URL = "https://oauth.sensiapi.io/token"
API_URL = "https://sensiapi.io"
SOCKET_URL = "https://rt.sensiapi.io"
CLIENT_ID = "fleet"
CLIENT_SECRET = "JLFjJmketRhj>M9uoDhusYKyi?zUyNqhGB)H2XiwLEF#KcGKrRD2JZsDQ7ufNven"
SOCKET_CAPABILITIES_QUERY = (
    "?capabilities=display_humidity,operating_mode_settings,"
    "fan_mode_settings,indoor_equipment,outdoor_equipment,indoor_stages,"
    "outdoor_stages,continuous_backlight,degrees_fc,display_time,"
    "keypad_lockout,temp_offset,compressor_lockout,boost,heat_cycle_rate,"
    "heat_cycle_rate_steps,cool_cycle_rate,cool_cycle_rate_steps,"
    "aux_cycle_rate,aux_cycle_rate_steps,early_start,min_heat_setpoint,"
    "max_heat_setpoint,min_cool_setpoint,max_cool_setpoint,circulating_fan,"
    "humidity_control,humidity_offset,humidity_offset_lower_bound,"
    "humidity_offset_upper_bound,temp_offset_lower_bound,"
    "temp_offset_upper_bound,lowest_heat_setpoint_ceiling,"
    "heat_setpoint_ceiling,highest_cool_setpoint_floor,cool_setpoint_floor"
)


@dataclass
class ThermostatSummary:
    """Basic thermostat details discovered from websocket state."""

    icd_id: str
    name: str
    display_temp: Any
    scale: str
    raw: dict[str, Any]


def mask(value: str | None, keep: int = 4) -> str:
    """Mask secrets for console output."""
    if not value:
        return "<missing>"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def post_form(url: str, form_data: dict[str, str], headers: dict[str, str]) -> Any:
    """POST form data and return parsed JSON."""
    body = parse.urlencode(form_data).encode()
    req = request.Request(url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode())


def get_json(url: str, headers: dict[str, str]) -> Any:
    """GET JSON and return parsed body."""
    req = request.Request(url, headers=headers, method="GET")
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode())


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange the refresh token for a new access token."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "accept-language": "en-US,en;q=0.9",
        "accept": "*/*",
    }
    form_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return post_form(OAUTH_URL, form_data, headers)


def build_auth_headers(access_token: str) -> dict[str, str]:
    """Build auth headers for Sensi REST APIs."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


async def discover_thermostats(access_token: str, timeout: int) -> list[ThermostatSummary]:
    """Discover thermostats through the same websocket used by Home Assistant."""
    try:
        import socketio
    except ImportError as exc:
        raise RuntimeError(
            "python-socketio is not installed, so websocket discovery is unavailable."
        ) from exc

    discovered: dict[str, ThermostatSummary] = {}
    ready = asyncio.get_running_loop().create_future()
    sio = socketio.AsyncClient()

    @sio.on("*")
    async def any_event(event: str, data: Any) -> None:
        if event != "state" or not isinstance(data, list):
            return

        for item in data:
            if not isinstance(item, dict):
                continue
            icd_id = item.get("icd_id")
            if not icd_id:
                continue

            registration = item.get("registration", {})
            state = item.get("state", {})
            discovered[icd_id] = ThermostatSummary(
                icd_id=icd_id,
                name=registration.get("name", ""),
                display_temp=state.get("display_temp"),
                scale=state.get("display_scale", ""),
                raw=item,
            )

        if discovered and not ready.done():
            ready.set_result(True)

    await sio.connect(
        SOCKET_URL + SOCKET_CAPABILITIES_QUERY,
        headers={"Authorization": f"bearer {access_token}"},
        socketio_path="/thermostat",
        transports=["websocket"],
    )

    try:
        await asyncio.wait_for(ready, timeout=timeout)
    finally:
        await sio.disconnect()

    return list(discovered.values())


def print_json(title: str, payload: Any) -> None:
    """Print a JSON block."""
    print(f"\n{title}")
    print(json.dumps(payload, indent=2, sort_keys=True))


async def async_main() -> int:
    """Run the probe."""
    parser = argparse.ArgumentParser(
        description=(
            "Probe Sensi auth, websocket discovery, and room sensor summary "
            "using a refresh token."
        )
    )
    parser.add_argument(
        "--refresh-token",
        default=os.environ.get("SENSI_REFRESH_TOKEN"),
        help="Sensi refresh token. Defaults to SENSI_REFRESH_TOKEN.",
    )
    parser.add_argument(
        "--icd-id",
        default=os.environ.get("SENSI_ICD_ID"),
        help="Thermostat ICD ID. Defaults to SENSI_ICD_ID.",
    )
    parser.add_argument(
        "--scale",
        default=os.environ.get("SENSI_SCALE", "f"),
        choices=["f", "c", "F", "C"],
        help="Scale for sensor-summary requests. Defaults to f.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout in seconds for websocket discovery.",
    )
    parser.add_argument(
        "--skip-websocket",
        action="store_true",
        help="Skip websocket discovery and only do token + summary checks.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON payloads.",
    )
    args = parser.parse_args()

    if not args.refresh_token:
        print(
            "Missing refresh token. Pass --refresh-token or export "
            "SENSI_REFRESH_TOKEN.",
            file=sys.stderr,
        )
        return 2

    print(f"Using refresh token: {mask(args.refresh_token)}")

    try:
        token_payload = refresh_access_token(args.refresh_token)
    except error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"Token refresh failed: HTTP {exc.code}\n{body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Token refresh failed: {exc}", file=sys.stderr)
        return 1

    access_token = token_payload.get("access_token")
    next_refresh_token = token_payload.get("refresh_token")
    user_id = token_payload.get("user_id")

    print(f"Access token acquired: {mask(access_token)}")
    print(f"Returned refresh token: {mask(next_refresh_token)}")
    print(f"User id: {user_id}")

    if args.raw:
        print_json("Token payload", token_payload)

    discovered: list[ThermostatSummary] = []
    if not args.skip_websocket:
        try:
            discovered = await discover_thermostats(access_token, args.timeout)
        except Exception as exc:
            print(f"\nWebsocket discovery skipped/failed: {exc}", file=sys.stderr)
        else:
            print("\nDiscovered thermostats")
            for thermostat in discovered:
                print(
                    f"- {thermostat.name or '<unnamed>'} | "
                    f"{thermostat.icd_id} | "
                    f"display_temp={thermostat.display_temp}{thermostat.scale}"
                )
            if args.raw:
                print_json(
                    "Discovered websocket payloads",
                    [thermostat.raw for thermostat in discovered],
                )

    icd_id = args.icd_id or (discovered[0].icd_id if discovered else None)
    if not icd_id:
        print(
            "\nNo thermostat id available. Pass --icd-id or use websocket "
            "discovery in an environment with python-socketio installed.",
            file=sys.stderr,
        )
        return 0

    summary_url = f"{API_URL}/thermostat/v2/{icd_id}/sensor-summary?scale={args.scale}"
    try:
        summary_payload = get_json(summary_url, build_auth_headers(access_token))
    except error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(
            f"\nSensor summary failed for {icd_id}: HTTP {exc.code}\n{body}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"\nSensor summary failed for {icd_id}: {exc}", file=sys.stderr)
        return 1

    sensors = summary_payload.get("sensors", [])
    print(f"\nSensor summary for {icd_id}")
    print(
        f"- active_control_group_id: "
        f"{summary_payload.get('active_control_group_id')}"
    )
    print(f"- sensor_count: {len(sensors)}")
    for sensor in sensors:
        print(
            f"- {sensor.get('name', sensor.get('id'))}: "
            f"type={sensor.get('type')} "
            f"temp={sensor.get('temperature')} "
            f"humidity={sensor.get('humidity')} "
            f"active={sensor.get('active')}"
        )

    if args.raw:
        print_json("Sensor summary payload", summary_payload)

    return 0


def main() -> int:
    """Entrypoint."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
