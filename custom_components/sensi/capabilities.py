# """Sensi Thermosta capabilities."""

# from __future__ import annotations

# import asyncio
# from collections.abc import Callable, Mapping
# from typing import Any


# class ThermostatCapabilities:
#     """Representation of Sensi thermostat capabilities."""

#     display_humidity: bool = False
#     system_modes: list[str] = []
#     fan_modes: list[str] = []
#     indoor_equipment: str = ""
#     outdoor_equipment: str = ""
#     indoor_stages: int = 0
#     outdoor_stages: int = 0
#     continuous_backlight: bool = False
#     display_scale: bool = False
#     display_time: bool = False
#     keypad_lockout: bool = False
#     temp_offset: bool = False
#     temp_offset_lower_bound: float = 0.0
#     temp_offset_upper_bound: float = 0.0
#     humidity_offset: bool = False
#     humidity_offset_lower_bound: float = 0.0
#     humidity_offset_upper_bound: float = 0.0
#     compressor_lockout: bool = False
#     boost: bool = False
#     heat_cycle_rate: bool = False
#     heat_cycle_rate_steps: list = []
#     cool_cycle_rate: bool = False
#     cool_cycle_rate_steps: list = []
#     aux_cycle_rate: bool = False
#     aux_cycle_rate_steps: list = []
#     early_start: bool = False
#     min_heat_setpoint: float = 0.0
#     heat_temperature_limit_floor: float = 0.0
#     max_heat_setpoint: float = 0.0
#     heat_temperature_limits: bool = False
#     min_cool_setpoint: float = 0.0
#     cool_temperature_limit_ceiling: float = 0.0
#     cool_temperature_limits: bool = False
#     max_cool_setpoint: float = 0.0
#     # circulatingFan: circulatingFanCapabilities
#     # humidityControlCapabilities: humidityControlCapabilities
#     eim_control_capable: bool = False
