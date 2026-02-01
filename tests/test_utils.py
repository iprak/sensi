"""Tests for Sensi utils module."""

import pytest

from custom_components.sensi.client import ActionResponse, raise_if_error
from custom_components.sensi.utils import bool_to_onoff, to_bool, to_float, to_int
from homeassistant.exceptions import HomeAssistantError


class TestToInt:
    """Test cases for to_int function."""

    def test_to_int_with_integer(self):
        """Test conversion of integer value."""
        assert to_int(42, 0) == 42

    def test_to_int_with_float(self):
        """Test conversion of float value."""
        assert to_int(42.7, 0) == 42

    def test_to_int_with_negative_integer(self):
        """Test conversion of negative integer."""
        assert to_int(-10, 0) == -10

    def test_to_int_with_negative_float(self):
        """Test conversion of negative float."""
        assert to_int(-10.9, 0) == -10

    def test_to_int_with_zero(self):
        """Test conversion of zero."""
        assert to_int(0, 99) == 0

    def test_to_int_with_invalid_string(self):
        """Test conversion of invalid string returns default."""
        assert to_int("not a number", 100) == 100

    def test_to_int_with_none(self):
        """Test conversion of None returns default."""
        assert to_int(None, 50) == 50

    def test_to_int_with_empty_string(self):
        """Test conversion of empty string returns default."""
        assert to_int("", 75) == 75

    def test_to_int_with_float_default(self):
        """Test that float default is converted to int."""
        assert to_int("invalid", 42.5) == 42.5

    def test_to_int_with_large_number(self):
        """Test conversion of large number."""
        assert to_int(1000000, 0) == 1000000

    def test_to_int_with_scientific_notation(self):
        """Test conversion of scientific notation float."""
        assert to_int(1e3, 0) == 1000


class TestToFloat:
    """Test cases for to_float function."""

    def test_to_float_with_integer(self):
        """Test conversion of integer value."""
        assert to_float(42, 0.0) == 42.0

    def test_to_float_with_float(self):
        """Test conversion of float value."""
        assert to_float(42.7, 0.0) == 42.7

    def test_to_float_with_negative_integer(self):
        """Test conversion of negative integer."""
        assert to_float(-10, 0.0) == -10.0

    def test_to_float_with_negative_float(self):
        """Test conversion of negative float."""
        assert to_float(-10.9, 0.0) == -10.9

    def test_to_float_with_zero(self):
        """Test conversion of zero."""
        assert to_float(0, 99.5) == 0.0

    def test_to_float_with_invalid_string(self):
        """Test conversion of invalid string returns default."""
        assert to_float("not a number", 100.5) == 100.5

    def test_to_float_with_none(self):
        """Test conversion of None returns default."""
        assert to_float(None, 50.5) == 50.5

    def test_to_float_with_empty_string(self):
        """Test conversion of empty string returns default."""
        assert to_float("", 75.5) == 75.5

    def test_to_float_with_precision(self):
        """Test conversion preserves precision."""
        assert to_float(3.14159, 0.0) == 3.14159

    def test_to_float_with_very_small_number(self):
        """Test conversion of very small number."""
        assert to_float(0.0001, 0.0) == 0.0001

    def test_to_float_with_scientific_notation(self):
        """Test conversion of scientific notation."""
        assert to_float(1e-3, 0.0) == 0.001


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("yes", True),
        ("YES", True),
        ("Yes", True),
        ("on", True),
        ("ON", True),
        ("On", True),
        ("false", False),
        ("no", False),
        ("off", False),
        ("", False),
        (None, False),
        ("random", False),
        (True, True),
        (False, False),
    ],
)
def test_to_bool(input_val, expected) -> None:
    """Test to_bool function."""
    assert to_bool(input_val) == expected


class TestBoolToOnoff:
    """Test cases for bool_to_onoff function."""

    def test_bool_to_onoff_with_true(self):
        """Test conversion of True to 'on'."""
        assert bool_to_onoff(True) == "on"

    def test_bool_to_onoff_with_false(self):
        """Test conversion of False to 'off'."""
        assert bool_to_onoff(False) == "off"


class TestRaiseIfError:
    """Test cases for raise_if_error function."""

    def test_raise_if_error_with_no_error(self):
        """Test no exception raised when error is None."""
        # Should not raise
        raise_if_error(ActionResponse(None, {}), "property", "value")

    def test_raise_if_error_with_no_error_empty_string(self):
        """Test no exception raised when error is empty string."""
        # Should not raise
        raise_if_error(ActionResponse("", {}), "property", "value")

    def test_raise_if_error_with_error(self):
        """Test exception raised when error is present."""
        with pytest.raises(HomeAssistantError) as exc_info:
            raise_if_error(
                ActionResponse("Something went wrong", None), "temperature", 72
            )
        assert "Unable to set temperature to 72" in str(exc_info.value)
        assert "Something went wrong" in str(exc_info.value)

    def test_raise_if_error_with_complex_error_message(self):
        """Test exception includes complex error message."""
        with pytest.raises(HomeAssistantError) as exc_info:
            raise_if_error(
                ActionResponse("API returned status 500", None), "humidity", 50
            )
        assert "Unable to set humidity to 50" in str(exc_info.value)
        assert "API returned status 500" in str(exc_info.value)

    def test_raise_if_error_preserves_value_in_message(self):
        """Test exception message includes the value."""
        with pytest.raises(HomeAssistantError) as exc_info:
            raise_if_error(ActionResponse("Failed", None), "mode", "heat")
        assert "heat" in str(exc_info.value)

    def test_raise_if_error_with_false_error(self):
        """Test no exception raised when error is False."""
        # Should not raise
        raise_if_error(ActionResponse(False, {}), "property", "value")

    def test_raise_if_error_with_zero_error(self):
        """Test no exception raised when error is 0."""
        # Should not raise
        raise_if_error(ActionResponse(0, {}), "property", "value")
