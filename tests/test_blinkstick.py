"""
Tests for BlinkStick class and device discovery functions.

These tests cover:
- Device variant constants (BLINKSTICK, BLINKSTICK_PRO, etc.)
- Device discovery functions (find_all, find_first, find_by_serial)
- _determine_rgb method with various input types
"""

import pytest
from unittest import mock
import blinkstick.blinkstick as bs


class TestDeviceConstants:
    """Tests for device variant constants."""

    def test_unknown_constant(self):
        """Test UNKNOWN constant value."""
        assert bs.BlinkStick.UNKNOWN == 0

    def test_blinkstick_constant(self):
        """Test BLINKSTICK constant value."""
        assert bs.BlinkStick.BLINKSTICK == 1

    def test_pro_constant(self):
        """Test BLINKSTICK_PRO constant value."""
        assert bs.BlinkStick.BLINKSTICK_PRO == 2

    def test_strip_constant(self):
        """Test BLINKSTICK_STRIP constant value."""
        assert bs.BlinkStick.BLINKSTICK_STRIP == 3

    def test_square_constant(self):
        """Test BLINKSTICK_SQUARE constant value."""
        assert bs.BlinkStick.BLINKSTICK_SQUARE == 4

    def test_nano_constant(self):
        """Test BLINKSTICK_NANO constant value."""
        assert bs.BlinkStick.BLINKSTICK_NANO == 5

    def test_flex_constant(self):
        """Test BLINKSTICK_FLEX constant value."""
        assert bs.BlinkStick.BLINKSTICK_FLEX == 6


class TestFindFunctions:
    """Tests for device discovery functions."""

    def test_find_first_returns_none_no_device(self):
        """Test find_first returns None when no device is found."""
        with mock.patch('blinkstick.blinkstick._find_blicksticks') as mock_find:
            mock_find.return_value = None
            result = bs.find_first()
            assert result is None

    def test_find_all_returns_empty_list_no_device(self):
        """Test find_all returns empty list when no device is found."""
        with mock.patch('blinkstick.blinkstick._find_blicksticks') as mock_find:
            mock_find.return_value = []
            result = bs.find_all()
            assert result == []

    def test_find_by_serial_returns_none_no_device(self):
        """Test find_by_serial returns None when serial not found."""
        with mock.patch('blinkstick.blinkstick._find_blicksticks') as mock_find:
            mock_find.return_value = []
            result = bs.find_by_serial('BS123456-1.0')
            assert result is None

    @mock.patch('blinkstick.blinkstick.BlinkStick')
    def test_find_first_creates_device(self, mock_blinkstick_class):
        """Test find_first creates BlinkStick instance."""
        mock_device = mock.MagicMock()
        with mock.patch('blinkstick.blinkstick._find_blicksticks') as mock_find:
            mock_find.return_value = mock_device
            result = bs.find_first()
            assert result is not None
            mock_blinkstick_class.assert_called_once()


class TestDetermineRgb:
    """Tests for _determine_rgb method."""

    def test_rgb_integers(self):
        """Test _determine_rgb with integer RGB values."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(red=255, green=128, blue=64)
        assert red == 255
        assert green == 128
        assert blue == 64

    def test_rgb_zero(self):
        """Test _determine_rgb with zero values."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(red=0, green=0, blue=0)
        assert red == 0
        assert green == 0
        assert blue == 0

    def test_hex_color(self):
        """Test _determine_rgb with hex color."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(hex='#ff0000')
        assert red == 255
        assert green == 0
        assert blue == 0

    def test_color_name(self):
        """Test _determine_rgb with color name."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(name='blue')
        assert red == 0
        assert green == 0
        assert blue == 255

    def test_random_color(self):
        """Test _determine_rgb with 'random' color name."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(name='random')
        assert 0 <= red <= 255
        assert 0 <= green <= 255
        assert 0 <= blue <= 255

    def test_invalid_hex_defaults_to_black(self):
        """Test _determine_rgb with invalid hex defaults to black."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(hex='invalid')
        assert red == 0
        assert green == 0
        assert blue == 0

    def test_invalid_name_defaults_to_black(self):
        """Test _determine_rgb with invalid color name defaults to black."""
        stick = bs.BlinkStick()
        red, green, blue = stick._determine_rgb(name='notacolor')
        assert red == 0
        assert green == 0
        assert blue == 0


class TestInverseMode:
    """Tests for inverse mode functionality."""

    def test_inverse_default_false(self):
        """Test that inverse defaults to False."""
        stick = bs.BlinkStick()
        assert stick.inverse is False

    def test_set_inverse_true(self):
        """Test setting inverse to True."""
        stick = bs.BlinkStick()
        stick.set_inverse(True)
        assert stick.inverse is True

    def test_set_inverse_false(self):
        """Test setting inverse to False."""
        stick = bs.BlinkStick()
        stick.set_inverse(False)
        assert stick.inverse is False

    def test_get_inverse(self):
        """Test get_inverse method."""
        stick = bs.BlinkStick()
        stick.set_inverse(True)
        assert stick.get_inverse() is True


class TestMaxRgbValue:
    """Tests for max_rgb_value functionality."""

    def test_max_rgb_value_default_255(self):
        """Test that max_rgb_value defaults to 255."""
        stick = bs.BlinkStick()
        assert stick.max_rgb_value == 255

    def test_set_max_rgb_value(self):
        """Test setting max_rgb_value."""
        stick = bs.BlinkStick()
        stick.set_max_rgb_value(200)
        assert stick.max_rgb_value == 200

    def test_get_max_rgb_value(self):
        """Test get_max_rgb_value method."""
        stick = bs.BlinkStick()
        stick.set_max_rgb_value(200)
        assert stick.get_max_rgb_value(200) == 200


class TestErrorReporting:
    """Tests for error_reporting functionality."""

    def test_error_reporting_default_true(self):
        """Test that error_reporting defaults to True."""
        stick = bs.BlinkStick()
        assert stick.error_reporting is True

    def test_set_error_reporting_false(self):
        """Test setting error_reporting to False."""
        stick = bs.BlinkStick(error_reporting=False)
        assert stick.error_reporting is False

    def test_set_error_reporting_method(self):
        """Test set_error_reporting method."""
        stick = bs.BlinkStick()
        stick.set_error_reporting(False)
        assert stick.error_reporting is False


class TestRemapFunctions:
    """Tests for color remapping helper functions."""

    def test_remap_color_same_max(self):
        """Test _remap_color with max_value=255."""
        result = bs._remap_color(128, 255)
        assert result == 128

    def test_remap_color_red_to_128(self):
        """Test _remap_color with red to lower max."""
        result = bs._remap_color(255, 128)
        assert result == 128

    def test_remap_color_zero(self):
        """Test _remap_color with zero value."""
        result = bs._remap_color(0, 255)
        assert result == 0

    def test_remap_color_reverse_same_max(self):
        """Test _remap_color_reverse with max_value=255."""
        result = bs._remap_color_reverse(128, 255)
        assert result == 128

    def test_remap_color_reverse_from_128_to_255(self):
        """Test _remap_color_reverse with 128 to 255."""
        result = bs._remap_color_reverse(128, 128)
        assert result == 255

    def test_remap_rgb_value(self):
        """Test _remap_rgb_value function."""
        result = bs._remap_rgb_value([255, 128, 64], 255)
        assert result == [255, 128, 64]

    def test_remap_rgb_value_reduced_max(self):
        """Test _remap_rgb_value with reduced max."""
        result = bs._remap_rgb_value([255, 255, 255], 128)
        assert result == [128, 128, 128]

    def test_remap_rgb_value_reverse(self):
        """Test _remap_rgb_value_reverse function."""
        result = bs._remap_rgb_value_reverse([128, 128, 128], 128)
        assert result == [255, 255, 255]
