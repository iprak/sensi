"""Tests for Sensi client component."""

from custom_components.sensi.client import round_humidity


class TestRoundHumidity:
    """Test cases for round_humidity function."""

    def test_round_up_to_nearest_5(self):
        """Test rounding up to nearest 5."""
        # 12 -> 10, then 14 -> 15
        assert round_humidity(14, 10) == 15

    def test_round_down_to_nearest_5(self):
        """Test rounding down to nearest 5."""
        # 12 -> 10
        assert round_humidity(12, 15) == 10

    def test_already_multiple_of_5(self):
        """Test when humidity is already a multiple of 5."""
        # 20 -> 20
        assert round_humidity(20, 10) == 20

    def test_humidity_greater_than_current_exact_match(self):
        """Test when humidity > current and rounded value equals current."""
        # If current is 20 and we want 22, rounded would be 20
        # Since 20 == current, we add 5 -> 25
        assert round_humidity(22, 20) == 25

    def test_humidity_less_than_current_exact_match(self):
        """Test when humidity < current and rounded value equals current."""
        # If current is 20 and we want 18, rounded would be 20
        # Since 20 == current, we subtract 5 -> 15
        assert round_humidity(18, 20) == 15

    def test_humidity_greater_than_current_normal(self):
        """Test when humidity > current and rounded value differs from current."""
        # If current is 10 and we want 14, rounded is 15
        # Since 15 != 10, return 15
        assert round_humidity(14, 10) == 15

    def test_humidity_less_than_current_normal(self):
        """Test when humidity < current and rounded value differs from current."""
        # If current is 40 and we want 32, rounded is 30
        # Since 30 != 40, return 30
        assert round_humidity(32, 40) == 30

    def test_humidity_equal_to_current(self):
        """Test when humidity equals current."""
        # No change should occur
        assert round_humidity(20, 20) == 20

    def test_edge_case_minimum_humidity(self):
        """Test at minimum humidity levels."""
        # If current is 5 and we want 7, rounded is 5
        # Since 5 == current, we add 5 -> 10
        assert round_humidity(7, 5) == 10

    def test_edge_case_maximum_humidity(self):
        """Test at maximum humidity levels."""
        # If current is 50 and we want 48, rounded is 50
        # Since 50 == current, we subtract 5 -> 45
        assert round_humidity(48, 50) == 45

    def test_edge_case_exact_midpoint_rounds_up(self):
        """Test exact midpoint value rounds to even (Python default)."""
        # 12.5 rounds to 12, 17.5 rounds to 18 (banker's rounding)
        # 12 * 5 = 60 -> 10, 13 * 5 = 65 -> 15, 17 * 5 = 85 -> 20
        assert round_humidity(13, 5) == 15

    def test_humidity_slightly_above_multiple_of_5(self):
        """Test humidity slightly above a multiple of 5."""
        # 21 -> 20
        assert round_humidity(21, 10) == 20

    def test_humidity_slightly_below_multiple_of_5(self):
        """Test humidity slightly below a multiple of 5."""
        # 19 -> 20
        assert round_humidity(19, 10) == 20

    def test_from_docstring_example_1(self):
        """Test example from docstring: 12 -> 10."""
        assert round_humidity(12, 15) == 10

    def test_from_docstring_example_2(self):
        """Test example from docstring: 14 -> 15."""
        assert round_humidity(14, 10) == 15

    def test_from_docstring_example_3(self):
        """Test example from docstring: 17 -> 15."""
        assert round_humidity(17, 20) == 15

    def test_from_docstring_example_4(self):
        """Test example from docstring: 20 -> 20."""
        assert round_humidity(20, 10) == 20

    def test_range_5_to_10(self):
        """Test transitioning from 5 to 10."""
        # If current is 5 and we want 10, no rounding needed
        assert round_humidity(10, 5) == 10

    def test_range_45_to_50(self):
        """Test transitioning from 45 to 50."""
        # If current is 45 and we want 50, no rounding needed
        assert round_humidity(50, 45) == 50

    def test_large_jump_up(self):
        """Test large jump up from current humidity."""
        # If current is 10 and we want 35, rounded is 35
        assert round_humidity(35, 10) == 35

    def test_large_jump_down(self):
        """Test large jump down from current humidity."""
        # If current is 50 and we want 15, rounded is 15
        assert round_humidity(15, 50) == 15
