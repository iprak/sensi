"""Tests for Sensi client component."""

from custom_components.sensi.client import round_humidity


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
