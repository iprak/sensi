"""Tests for Sensi client component."""

from dataclasses import asdict
from unittest.mock import patch

import pytest

from custom_components.sensi.client import ActionResponse, round_humidity
from custom_components.sensi.data import OperatingMode
from custom_components.sensi.event import (
    SetCirculatingFanEvent,
    SetCirculatingFanEventValue,
    SetHumidityEvent,
    SetHumidityEventValue,
    SetOperatingModeEvent,
    SetTemperatureEvent,
    SetTemperatureEventSuccess,
)


class TestRoundHumidity:
    """Test cases for round_humidity function."""

    # Basic rounding tests with step=5
    def test_round_up_to_nearest_5(self):
        """Test rounding up to nearest 5."""
        # humidity=14, current=10, step=5 -> rounds to 15
        assert round_humidity(14, 10, 5) == 15

    def test_round_down_to_nearest_5(self):
        """Test rounding down to nearest 5."""
        # humidity=12, current=15, step=5 -> rounds to 10
        assert round_humidity(12, 15, 5) == 10

    def test_already_multiple_of_5(self):
        """Test when humidity is already a multiple of 5."""
        # humidity=20, current=10, step=5 -> stays 20
        assert round_humidity(20, 10, 5) == 20

    # Tests for humidity > current_humidity
    def test_humidity_greater_than_current_exact_match(self):
        """Test when humidity > current and rounded value equals current."""
        # humidity=22, current=20, step=5 -> rounded to 20 == current, add step -> 25
        assert round_humidity(22, 20, 5) == 25

    def test_humidity_greater_than_current_normal(self):
        """Test when humidity > current and rounded value differs from current."""
        # humidity=14, current=10, step=5 -> rounded to 15 != 10, return 15
        assert round_humidity(14, 10, 5) == 15

    def test_humidity_greater_than_current_add_step(self):
        """Test when increasing humidity and need to add step."""
        # humidity=16, current=10, step=5 -> rounded to 15 != 10, return 15
        assert round_humidity(16, 10, 5) == 15

    # Tests for humidity < current_humidity
    def test_humidity_less_than_current_exact_match(self):
        """Test when humidity < current and rounded value equals current."""
        # humidity=18, current=20, step=5 -> rounded to 20 == current, subtract step -> 15
        assert round_humidity(18, 20, 5) == 15

    def test_humidity_less_than_current_normal(self):
        """Test when humidity < current and rounded value differs from current."""
        # humidity=32, current=40, step=5 -> rounded to 30 != 40, return 30
        assert round_humidity(32, 40, 5) == 30

    def test_humidity_less_than_current_subtract_step(self):
        """Test when decreasing humidity and need to subtract step."""
        # humidity=34, current=40, step=5 -> rounded to 35 != 40, return 35
        assert round_humidity(34, 40, 5) == 35

    # Tests for humidity == current_humidity
    def test_humidity_equal_to_current(self):
        """Test when humidity equals current - no change should occur."""
        assert round_humidity(20, 20, 5) == 20

    def test_humidity_equal_to_current_different_step(self):
        """Test when humidity equals current with different step."""
        assert round_humidity(30, 30, 10) == 30

    # Edge cases with different step values
    def test_step_10(self):
        """Test with step=10."""
        # humidity=22, current=10, step=10 -> rounded to 20 != 10, return 20
        assert round_humidity(22, 10, 10) == 20

    def test_step_10_exact_match(self):
        """Test with step=10 where rounded equals current."""
        # humidity=15, current=20, step=10 -> rounded to 20 == current, subtract -> 10
        assert round_humidity(15, 20, 10) == 10

    def test_step_1(self):
        """Test with step=1 (minimum practical step)."""
        # humidity=22, current=20, step=1 -> rounded to 22 != 20, return 22
        assert round_humidity(22, 20, 1) == 22

    # Edge cases at boundaries
    def test_edge_case_minimum_humidity(self):
        """Test at minimum humidity levels."""
        # humidity=7, current=5, step=5 -> rounded to 5 == current, add step -> 10
        assert round_humidity(7, 5, 5) == 10

    def test_edge_case_maximum_humidity(self):
        """Test at maximum humidity levels."""
        # humidity=48, current=50, step=5 -> rounded to 50 == current, subtract -> 45
        assert round_humidity(48, 50, 5) == 45

    def test_edge_case_zero_humidity(self):
        """Test with humidity at 0."""
        # humidity=0, current=10, step=5 -> rounded to 0 != 10, return 0
        assert round_humidity(0, 10, 5) == 0

    def test_edge_case_100_humidity(self):
        """Test with humidity at 100."""
        # humidity=100, current=50, step=5 -> rounded to 100 != 50, return 100
        assert round_humidity(100, 50, 5) == 100

    # Docstring examples
    def test_from_docstring_example_1(self):
        """Test example from docstring: 12 -> 10."""
        assert round_humidity(12, 15, 5) == 10

    def test_from_docstring_example_2(self):
        """Test example from docstring: 14 -> 15."""
        assert round_humidity(14, 10, 5) == 15

    def test_from_docstring_example_3(self):
        """Test example from docstring: 17 -> 15."""
        assert round_humidity(17, 20, 5) == 15

    def test_from_docstring_example_4(self):
        """Test example from docstring: 20 -> 20."""
        assert round_humidity(20, 10, 5) == 20

    # Rounding edge cases (banker's rounding)
    def test_midpoint_rounding_up(self):
        """Test midpoint value that rounds up."""
        # humidity=13, current=10, step=5 -> 13/5 = 2.6 -> rounds to 3 -> 15
        assert round_humidity(13, 10, 5) == 15

    def test_midpoint_rounding_down(self):
        """Test midpoint value that rounds down."""
        # humidity=12, current=10, step=5 -> 12/5 = 2.4 -> rounds to 2 -> 10
        assert round_humidity(12, 10, 5) == 15

    # Large jumps
    def test_large_jump_up(self):
        """Test large jump up from current humidity."""
        # humidity=35, current=10, step=5 -> rounded to 35 != 10, return 35
        assert round_humidity(35, 10, 5) == 35

    def test_large_jump_down(self):
        """Test large jump down from current humidity."""
        # humidity=15, current=50, step=5 -> rounded to 15 != 50, return 15
        assert round_humidity(15, 50, 5) == 15

    # Various step sizes
    def test_step_2(self):
        """Test with step=2."""
        # humidity=23, current=20, step=2 -> rounded to 24 != 20, return 24
        assert round_humidity(23, 20, 2) == 24

    def test_step_3(self):
        """Test with step=3."""
        # humidity=25, current=20, step=3 -> rounded to 24 != 20, return 24
        assert round_humidity(25, 20, 3) == 24

    # More complex scenarios
    def test_complex_scenario_going_up(self):
        """Test complex scenario with step=5 going up."""
        # humidity=11, current=5, step=5 -> 11/5 = 2.2 -> rounds to 2 -> 10
        # 10 == current+5, so return 10
        assert round_humidity(11, 5, 5) == 10

    def test_small_values(self):
        """Test with small humidity values."""
        assert round_humidity(2, 5, 1) == 2

    def test_repeated_same_value(self):
        """Test setting same humidity multiple times."""
        assert round_humidity(25, 25, 5) == 25
        assert round_humidity(25, 25, 5) == 25


class TestSetTemperature:
    """Test async_set_temperature method."""

    @pytest.mark.parametrize(
        ("value", "mode", "expected_error"),
        [
            (45, OperatingMode.HEAT, None),
            (50, OperatingMode.HEAT, None),
            (45, OperatingMode.HEAT, "Failed to set temperature"),
            (78, OperatingMode.COOL, None),
            (75, OperatingMode.COOL, None),
            (78, OperatingMode.COOL, "Failed to set temperature"),
        ],
    )
    async def test_set_temperature(
        self,
        mock_device,
        mock_coordinator,
        value: float,
        mode: OperatingMode,
        expected_error: str | None,
    ) -> None:
        """Test set_temperature method."""

        if expected_error:
            mock_response = None
            expected_response_data = None
        else:
            mock_response = {
                "current_temp": mock_device.state.display_temp,
                "mode": mode.value,  # mock_device.state.operating_mode.value
                "target_temp": value,
            }
            expected_response_data = SetTemperatureEventSuccess(**mock_response)

        expected_request = asdict(
            SetTemperatureEvent(
                mock_device.identifier,
                mock_device.state.display_scale,
                mode.value,
                value,
            )
        )

        with patch.object(
            mock_coordinator.client, "_async_invoke_setter"
        ) as mock_async_invoke_setter:
            mock_async_invoke_setter.return_value = ActionResponse(
                expected_error, mock_response
            )

            response = await mock_coordinator.client.async_set_temperature(
                mock_device, mode, value
            )

            mock_async_invoke_setter.assert_called_once_with(
                "set_temperature", expected_request
            )

            assert response.error is expected_error

            if not expected_error:
                assert response.data == expected_response_data

                if mode == OperatingMode.HEAT:
                    assert (
                        mock_device.state.current_heat_temp
                        == expected_response_data.target_temp
                    )
                if mode == OperatingMode.COOL:
                    assert (
                        mock_device.state.current_cool_temp
                        == expected_response_data.target_temp
                    )
            else:
                assert response.data is None

    async def test_set_temperature_OFF_state(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test set_temperature method when thermostat is OFF."""

        # Fake device to be in OFF state
        mock_device.state.operating_mode = OperatingMode.OFF

        with patch.object(
            mock_coordinator.client, "_async_invoke_setter"
        ) as mock_async_invoke_setter:
            response = await mock_coordinator.client.async_set_temperature(
                mock_device, OperatingMode.HEAT, 45
            )

            mock_async_invoke_setter.assert_not_called()
            assert response.error
            assert response.data is None


@pytest.mark.parametrize(
    ("enabled", "humidity", "expected_error"),
    [(True, 45, None), (False, 50, None), (True, 45, "Failed to set humidification")],
)
async def test_async_set_humidification(
    mock_device_with_humidification, mock_coordinator, enabled, humidity, expected_error
) -> None:
    """Test of set_humidification method."""

    mock_response = None if expected_error else {}
    expected_request = asdict(
        SetHumidityEvent(
            mock_device_with_humidification.identifier,
            SetHumidityEventValue(enabled, humidity),
        )
    )

    with patch.object(
        mock_coordinator.client, "_async_invoke_setter"
    ) as mock_async_invoke_setter:
        mock_async_invoke_setter.return_value = ActionResponse(
            expected_error, mock_response
        )

        response = await mock_coordinator.client.async_set_humidification(
            mock_device_with_humidification, enabled, humidity
        )

        mock_async_invoke_setter.assert_called_once_with(
            "set_humidification", expected_request
        )

        assert response.error is expected_error

        if not expected_error:
            assert response.data == mock_response
        else:
            assert response.data is None


@pytest.mark.parametrize(
    ("enabled"),
    [(True), (False)],
)
async def test_async_enable_humidification(
    mock_device_with_humidification, mock_coordinator, enabled
) -> None:
    """Test of enable_humidification method."""

    with patch.object(
        mock_coordinator.client, "async_set_humidification"
    ) as mock__set_humidification:
        await mock_coordinator.client.async_enable_humidification(
            mock_device_with_humidification, enabled
        )

        mock__set_humidification.assert_called_once_with(
            mock_device_with_humidification,
            enabled,
            mock_device_with_humidification.state.humidity_control.humidification.target_percent,
        )


@pytest.mark.parametrize(
    ("enabled", "duty_cycle"),
    [(True, 35), (False, 10)],
)
async def test_set_circulating_fan_mode(
    mock_device, mock_coordinator, enabled, duty_cycle
) -> None:
    """Test async_set_circulating_fan_mode."""

    enabled = True
    duty_cycle = 30

    with patch.object(
        mock_coordinator.client, "_async_invoke_setter"
    ) as mock_async_invoke_setter:
        mock_async_invoke_setter.return_value = ActionResponse(None, "")

        expected_request = asdict(
            SetCirculatingFanEvent(
                mock_device.identifier, SetCirculatingFanEventValue(enabled, duty_cycle)
            )
        )

        await mock_coordinator.client.async_set_circulating_fan_mode(
            mock_device, enabled, duty_cycle
        )

        mock_async_invoke_setter.assert_called_once_with(
            "set_circulating_fan", expected_request
        )

        assert mock_device.state.circulating_fan.enabled == enabled
        assert mock_device.state.circulating_fan.duty_cycle == duty_cycle


@pytest.mark.parametrize(
    ("response_error", "response_data", "expect_error"),
    [
        (None, None, True),
        ("Failed", None, True),
        (None, "not_accepted", True),
        (None, {"invalid_property": "cool"}, True),
        (None, "accepted", False),
        (None, {"mode": "heat"}, False),
    ],
)
async def test_async_set_operating_mode(
    mock_device, mock_coordinator, response_error, response_data, expect_error
) -> None:
    """Test async_set_operating_mode."""

    with patch.object(
        mock_coordinator.client, "_async_invoke_setter"
    ) as mock_async_invoke_setter:
        mock_async_invoke_setter.return_value = ActionResponse(
            response_error, response_data
        )

        mode = OperatingMode.HEAT
        expected_request = asdict(
            SetOperatingModeEvent(mock_device.identifier, mode.value)
        )
        mock_device.state.operating_mode = None  # Reset to ensure it gets updated

        response = await mock_coordinator.client.async_set_operating_mode(
            mock_device, mode
        )

        mock_async_invoke_setter.assert_called_once_with(
            "set_operating_mode", expected_request
        )
        if expect_error:
            assert response.error is not None
        else:
            assert response.error is None
            assert mock_device.state.operating_mode == OperatingMode.HEAT


@pytest.mark.parametrize(
    ("value", "should_succeed"),
    [(0, True), (5, True), (-5, True)],
)
async def test_async_set_temperature_offset_range(
    mock_device, mock_coordinator, value, should_succeed
) -> None:
    """Test async_set_temperature_offset value range validation."""

    with patch.object(
        mock_coordinator.client, "_async_invoke_setter"
    ) as mock_async_invoke_setter:
        mock_async_invoke_setter.return_value = ActionResponse(None, {})

        response = await mock_coordinator.client.async_set_temperature_offset(
            mock_device, value
        )

        if should_succeed:
            mock_async_invoke_setter.assert_called_once()
            assert response.error is None
            assert mock_device.state.temp_offset == value
        else:
            mock_async_invoke_setter.assert_not_called()
            assert response.error is not None
            assert "must be between" in response.error


@pytest.mark.parametrize(
    ("value", "should_succeed"),
    [(0, True), (25, True), (-25, True)],
)
async def test_async_set_humidity_offset_range(
    mock_device, mock_coordinator, value, should_succeed
) -> None:
    """Test async_set_humidity_offset value range validation."""

    with patch.object(
        mock_coordinator.client, "_async_invoke_setter"
    ) as mock_async_invoke_setter:
        mock_async_invoke_setter.return_value = ActionResponse(None, {})

        response = await mock_coordinator.client.async_set_humidity_offset(
            mock_device, value
        )

        if should_succeed:
            mock_async_invoke_setter.assert_called_once()
            assert response.error is None
            assert mock_device.state.humidity_offset == value
        else:
            mock_async_invoke_setter.assert_not_called()
            assert response.error is not None
            assert "must be between" in response.error
