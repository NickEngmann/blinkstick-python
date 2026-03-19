"""
Tests for blinkstick color utility functions.

These tests cover:
- _name_to_hex: Convert CSS color names to hex values
- _hex_to_rgb: Convert hex values to RGB tuples
- _normalize_hex: Normalize hex color strings
"""

import pytest
import blinkstick.blinkstick as bs


class TestNameToHex:
    """Tests for _name_to_hex method."""

    def test_white(self):
        """Test conversion of 'white' to hex."""
        stick = bs.BlinkStick()
        result = stick._name_to_hex('white')
        assert result == '#ffffff'

    def test_navy(self):
        """Test conversion of 'navy' to hex."""
        stick = bs.BlinkStick()
        result = stick._name_to_hex('navy')
        assert result == '#000080'

    def test_goldenrod(self):
        """Test conversion of 'goldenrod' to hex."""
        stick = bs.BlinkStick()
        result = stick._name_to_hex('goldenrod')
        assert result == '#daa520'

    def test_case_insensitive(self):
        """Test that color names are case-insensitive."""
        stick = bs.BlinkStick()
        assert stick._name_to_hex('WHITE') == '#ffffff'
        assert stick._name_to_hex('White') == '#ffffff'

    def test_invalid_color_raises_valueerror(self):
        """Test that invalid color names raise ValueError."""
        stick = bs.BlinkStick()
        with pytest.raises(ValueError) as exc_info:
            stick._name_to_hex('notacolor')
        assert 'notacolor' in str(exc_info.value)


class TestHexToRgb:
    """Tests for _hex_to_rgb method."""

    def test_full_hex(self):
        """Test conversion of full hex string."""
        stick = bs.BlinkStick()
        result = stick._hex_to_rgb('#000080')
        assert result == (0, 0, 128)

    def test_short_hex(self):
        """Test conversion of short hex string (3 digits)."""
        stick = bs.BlinkStick()
        result = stick._hex_to_rgb('#fff')
        assert result == (255, 255, 255)

    def test_uppercase_hex(self):
        """Test conversion with uppercase hex."""
        stick = bs.BlinkStick()
        result = stick._hex_to_rgb('#FF0000')
        assert result == (255, 0, 0)

    def test_mixed_case_hex(self):
        """Test conversion with mixed case hex."""
        stick = bs.BlinkStick()
        result = stick._hex_to_rgb('#DeAdBe')
        assert result == (222, 173, 190)

    def test_invalid_hex_raises_valueerror(self):
        """Test that invalid hex strings raise ValueError."""
        stick = bs.BlinkStick()
        with pytest.raises(ValueError) as exc_info:
            stick._hex_to_rgb('notahex')
        assert 'notahex' in str(exc_info.value)


class TestNormalizeHex:
    """Tests for _normalize_hex method."""

    def test_already_normalized(self):
        """Test hex string that is already normalized."""
        stick = bs.BlinkStick()
        result = stick._normalize_hex('#0099cc')
        assert result == '#0099cc'

    def test_uppercase_normalized(self):
        """Test uppercase hex is normalized to lowercase."""
        stick = bs.BlinkStick()
        result = stick._normalize_hex('#0099CC')
        assert result == '#0099cc'

    def test_short_hex_expanded(self):
        """Test 3-digit hex is expanded to 6 digits."""
        stick = bs.BlinkStick()
        result = stick._normalize_hex('#09c')
        assert result == '#0099cc'

    def test_short_uppercase_expanded(self):
        """Test short uppercase hex is expanded and lowercased."""
        stick = bs.BlinkStick()
        result = stick._normalize_hex('#09C')
        assert result == '#0099cc'

    def test_invalid_hex_raises_valueerror(self):
        """Test that invalid hex values raise ValueError."""
        stick = bs.BlinkStick()
        with pytest.raises(ValueError) as exc_info:
            stick._normalize_hex('0099cc')  # Missing #
        assert '0099cc' in str(exc_info.value)


class TestNameToRgb:
    """Tests for _name_to_rgb method."""

    def test_white_rgb(self):
        """Test conversion of 'white' to RGB tuple."""
        stick = bs.BlinkStick()
        result = stick._name_to_rgb('white')
        assert result == (255, 255, 255)

    def test_navy_rgb(self):
        """Test conversion of 'navy' to RGB tuple."""
        stick = bs.BlinkStick()
        result = stick._name_to_rgb('navy')
        assert result == (0, 0, 128)

    def test_goldenrod_rgb(self):
        """Test conversion of 'goldenrod' to RGB tuple."""
        stick = bs.BlinkStick()
        result = stick._name_to_rgb('goldenrod')
        assert result == (218, 165, 32)


class TestColorDictionary:
    """Tests for the _names_to_hex color dictionary."""

    def test_black_present(self):
        """Verify 'black' is in the color dictionary."""
        assert 'black' in bs.BlinkStick._names_to_hex
        assert bs.BlinkStick._names_to_hex['black'] == '#000000'

    def test_red_present(self):
        """Verify 'red' is in the color dictionary."""
        assert 'red' in bs.BlinkStick._names_to_hex
        assert bs.BlinkStick._names_to_hex['red'] == '#ff0000'

    def test_blue_present(self):
        """Verify 'blue' is in the color dictionary."""
        assert 'blue' in bs.BlinkStick._names_to_hex
        assert bs.BlinkStick._names_to_hex['blue'] == '#0000ff'

    def test_count(self):
        """Verify there are many colors defined."""
        assert len(bs.BlinkStick._names_to_hex) > 100
