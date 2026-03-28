"""Unit tests for blinkstick.py library functionality."""

import unittest
import sys
import os
from unittest.mock import patch

# Import the blinkstick module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blinkstick.blinkstick import (
    BlinkStick,
    BlinkStickException,
    _remap_rgb_value,
    _remap_color,
    _find_blicksticks,
    find_all,
    find_first,
    find_by_serial,
    get_blinkstick_package_version,
    VENDOR_ID,
    PRODUCT_ID,
)


class TestColorDefinitions(unittest.TestCase):
    """Test that color definitions exist and are correct."""

    def test_color_names_exist(self):
        """Test that color name definitions exist."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertIsInstance(bs._names_to_hex, dict)
        self.assertGreater(len(bs._names_to_hex), 100)

    def test_green_color_definition(self):
        """Test green color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['green'], '#008000')

    def test_red_color_definition(self):
        """Test red color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['red'], '#ff0000')

    def test_yellow_color_definition(self):
        """Test yellow color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['yellow'], '#ffff00')

    def test_blue_color_definition(self):
        """Test blue color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['blue'], '#0000ff')

    def test_black_color_definition(self):
        """Test black color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['black'], '#000000')

    def test_white_color_definition(self):
        """Test white color hex value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._names_to_hex['white'], '#ffffff')


class TestDefaultConfiguration(unittest.TestCase):
    """Test default BlinkStick configuration."""

    def test_class_attributes_exist(self):
        """Test that class attributes are defined."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertTrue(hasattr(bs, 'inverse'))
        self.assertTrue(hasattr(bs, 'error_reporting'))
        self.assertTrue(hasattr(bs, 'max_rgb_value'))

    def test_default_inverse(self):
        """Test default inverse mode."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertFalse(bs.inverse)

    def test_default_error_reporting(self):
        """Test default error reporting."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertTrue(bs.error_reporting)

    def test_default_max_rgb_value(self):
        """Test default max RGB value."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs.max_rgb_value, 255)

    def test_variant_constants_exist(self):
        """Test variant constants are defined."""
        self.assertEqual(BlinkStick.UNKNOWN, 0)
        self.assertEqual(BlinkStick.BLINKSTICK, 1)
        self.assertEqual(BlinkStick.BLINKSTICK_PRO, 2)
        self.assertEqual(BlinkStick.BLINKSTICK_STRIP, 3)
        self.assertEqual(BlinkStick.BLINKSTICK_SQUARE, 4)
        self.assertEqual(BlinkStick.BLINKSTICK_NANO, 5)
        self.assertEqual(BlinkStick.BLINKSTICK_FLEX, 6)

    def test_vendor_product_ids(self):
        """Test vendor and product IDs are defined."""
        self.assertEqual(VENDOR_ID, 0x20a0)
        self.assertEqual(PRODUCT_ID, 0x41e5)


class TestHexConversion(unittest.TestCase):
    """Test hexadecimal color conversion functions."""

    def test_normalize_hex_valid(self):
        """Test _normalize_hex with valid inputs."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._normalize_hex('#0099cc'), '#0099cc')
        self.assertEqual(bs._normalize_hex('#0099CC'), '#0099cc')
        self.assertEqual(bs._normalize_hex('#09c'), '#0099cc')
        self.assertEqual(bs._normalize_hex('#09C'), '#0099cc')

    def test_normalize_hex_invalid(self):
        """Test _normalize_hex with invalid inputs."""
        bs = BlinkStick.__new__(BlinkStick)
        
        with self.assertRaises(ValueError):
            bs._normalize_hex('0099cc')  # No # prefix
        with self.assertRaises(ValueError):
            bs._normalize_hex('#GGGGGG')  # Invalid hex chars
        with self.assertRaises(ValueError):
            bs._normalize_hex('#12345')  # Wrong length

    def test_hex_to_rgb_valid(self):
        """Test _hex_to_rgb with valid inputs."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._hex_to_rgb('#fff'), (255, 255, 255))
        self.assertEqual(bs._hex_to_rgb('#000'), (0, 0, 0))
        self.assertEqual(bs._hex_to_rgb('#ff0000'), (255, 0, 0))
        self.assertEqual(bs._hex_to_rgb('#00ff00'), (0, 255, 0))
        self.assertEqual(bs._hex_to_rgb('#0000ff'), (0, 0, 255))

    def test_hex_to_rgb_case_insensitive(self):
        """Test _hex_to_rgb is case insensitive."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._hex_to_rgb('#FF0000'), (255, 0, 0))
        self.assertEqual(bs._hex_to_rgb('#ff0000'), (255, 0, 0))
        self.assertEqual(bs._hex_to_rgb('#Ff0000'), (255, 0, 0))


class TestNameToRgb(unittest.TestCase):
    """Test color name to RGB conversion."""

    def test_name_to_rgb_green(self):
        """Test _name_to_rgb with green."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('green'), (0, 128, 0))

    def test_name_to_rgb_red(self):
        """Test _name_to_rgb with red."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('red'), (255, 0, 0))

    def test_name_to_rgb_blue(self):
        """Test _name_to_rgb with blue."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('blue'), (0, 0, 255))

    def test_name_to_rgb_black(self):
        """Test _name_to_rgb with black."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('black'), (0, 0, 0))

    def test_name_to_rgb_white(self):
        """Test _name_to_rgb with white."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('white'), (255, 255, 255))

    def test_name_to_rgb_case_insensitive(self):
        """Test _name_to_rgb is case insensitive."""
        bs = BlinkStick.__new__(BlinkStick)
        self.assertEqual(bs._name_to_rgb('RED'), (255, 0, 0))
        self.assertEqual(bs._name_to_rgb('red'), (255, 0, 0))
        self.assertEqual(bs._name_to_rgb('Red'), (255, 0, 0))

    def test_name_to_rgb_invalid(self):
        """Test _name_to_rgb with invalid color name."""
        bs = BlinkStick.__new__(BlinkStick)
        
        with self.assertRaises(ValueError):
            bs._name_to_rgb('notacolor')


class TestRemapFunctions(unittest.TestCase):
    """Test RGB value remapping functions."""

    def test_remap_color(self):
        """Test _remap_color basic functionality."""
        from blinkstick.blinkstick import _remap_color
        self.assertEqual(_remap_color(255, 255), 255)
        self.assertEqual(_remap_color(0, 255), 0)
        self.assertEqual(_remap_color(128, 255), 128)

    def test_remap_rgb_value(self):
        """Test _remap_rgb_value basic functionality."""
        result = _remap_rgb_value([255, 128, 0], 255)
        self.assertEqual(result, [255, 128, 0])

    def test_remap_rgb_value_scales(self):
        """Test _remap_rgb_value scales down values."""
        result = _remap_rgb_value([255, 200, 100], 128)
        self.assertEqual(result[0], 128)  # 255 -> 128
        self.assertTrue(0 <= result[1] <= 128)
        self.assertTrue(0 <= result[2] <= 128)


class TestNonIntegerInputs(unittest.TestCase):
    """Test handling of non-integer RGB inputs."""

    def test_string_integer_red(self):
        """Test red as string integer."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red='255', green=0, blue=0)
        self.assertEqual(result, (255.0, 0.0, 0.0))

    def test_string_integer_green(self):
        """Test green as string integer."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red=0, green='128', blue=0)
        self.assertEqual(result, (0.0, 128.0, 0.0))

    def test_string_integer_blue(self):
        """Test blue as string integer."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red=0, green=0, blue='255')
        self.assertEqual(result, (0.0, 0.0, 255.0))

    def test_float_rgb_values(self):
        """Test RGB as float values are converted and scaled."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red=128.5, green=64.2, blue=32.8)
        # Float values are converted via _remap_rgb_value which truncates
        self.assertEqual(result[0], 128)  # 128.5 -> 128
        self.assertEqual(result[1], 64)   # 64.2 -> 64
        self.assertEqual(result[2], 32)   # 32.8 -> 32

    def test_invalid_string_inputs(self):
        """Test invalid string inputs return zeros."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red='invalid', green=0, blue=0)
        self.assertEqual(result, (0.0, 0.0, 0.0))

    def test_none_inputs(self):
        """Test None inputs return zeros."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red=None, green=None, blue=None)
        self.assertEqual(result, (0.0, 0.0, 0.0))

    def test_mixed_integer_and_string(self):
        """Test mix of integer and string inputs."""
        bs = BlinkStick.__new__(BlinkStick)
        result = bs._determine_rgb(red=255, green='128', blue=0)
        self.assertEqual(result, (255.0, 128.0, 0.0))


class TestDeviceDetection(unittest.TestCase):
    """Test device detection functions (mocked)."""

    @patch('blinkstick.blinkstick._find_blicksticks')
    def test_find_first_mocked(self, mock_find):
        """Test find_first is called correctly."""
        mock_find.return_value = None
        result = find_first()
        self.assertIsNone(result)
        mock_find.assert_called_once_with(find_all=False)

    @patch('blinkstick.blinkstick._find_blicksticks')
    def test_find_all_empty(self, mock_find):
        """Test find_all with no devices."""
        mock_find.return_value = []
        result = find_all()
        self.assertEqual(result, [])
        mock_find.assert_called()  # Just verify it was called

    @patch('blinkstick.blinkstick._find_blicksticks')
    def test_find_by_serial_mocked(self, mock_find):
        """Test find_by_serial handles no devices."""
        mock_find.return_value = []
        result = find_by_serial(serial='test123')
        self.assertIsNone(result)


class TestGetVersion(unittest.TestCase):
    """Test package version retrieval."""

    def test_get_version_exists(self):
        """Test that get_blinkstick_package_version exists."""
        version = get_blinkstick_package_version()
        self.assertIsInstance(version, str)
        self.assertRegex(version, r'\d+\.\d+\.\d+')


class TestBlinkStickException(unittest.TestCase):
    """Test BlinkStickException class."""

    def test_exception_is_subclass_of_exception(self):
        """Test that BlinkStickException is a subclass of Exception."""
        self.assertTrue(issubclass(BlinkStickException, Exception))

    def test_exception_can_be_raised(self):
        """Test that BlinkStickException can be raised and caught."""
        with self.assertRaises(BlinkStickException):
            raise BlinkStickException("Test error")

    def test_exception_with_message(self):
        """Test exception message handling."""
        try:
            raise BlinkStickException("Device not found")
        except BlinkStickException as e:
            self.assertEqual(str(e), "Device not found")


class TestInvalidColorNames(unittest.TestCase):
    """Test handling of invalid color names."""

    def test_invalid_color_name_raises(self):
        """Test that invalid color names raise ValueError."""
        bs = BlinkStick.__new__(BlinkStick)
        
        with self.assertRaises(ValueError):
            bs._name_to_hex('notacolor123')

    def test_invalid_hex_raises(self):
        """Test that invalid hex colors raise ValueError."""
        bs = BlinkStick.__new__(BlinkStick)
        
        with self.assertRaises(ValueError):
            bs._hex_to_rgb('#GGGGGG')


class TestNamedColors(unittest.TestCase):
    """Test various named colors."""

    def test_common_colors(self):
        """Test common CSS color names."""
        bs = BlinkStick.__new__(BlinkStick)

        # Test a variety of common colors
        self.assertEqual(bs._names_to_hex['aliceblue'], '#f0f8ff')
        self.assertEqual(bs._names_to_hex['aquamarine'], '#7fffd4')
        self.assertEqual(bs._names_to_hex['coral'], '#ff7f50')
        self.assertEqual(bs._names_to_hex['goldenrod'], '#daa520')
        self.assertEqual(bs._names_to_hex['indigo'], '#4b0082')

    def test_all_color_names_lowercase(self):
        """Test that all color names are stored in lowercase."""
        bs = BlinkStick.__new__(BlinkStick)

        for name in bs._names_to_hex.keys():
            self.assertEqual(name, name.lower(), f"Color name '{name}' is not lowercase")


if __name__ == '__main__':
    unittest.main()
