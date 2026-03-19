"""
Tests for blinkstick-monitor.py configuration and utility functions.

These tests cover:
- Color constants (GREEN, RED, YELLOW, BLUE, OFF)
- Default configuration values
- is_blacklisted function
- is_quiet_hours function
"""

import pytest
from unittest import mock
from datetime import datetime
import sys
import os
import importlib.util

# Add parent directory to path for import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the module by executing the file as a script
spec = importlib.util.spec_from_file_location("blinkstick_monitor", os.path.join(os.path.dirname(__file__), '..', 'blinkstick-monitor.py'))
blinkstick_monitor = importlib.util.module_from_spec(spec)
sys.modules['blinkstick_monitor'] = blinkstick_monitor  # Make it importable for mocking
spec.loader.exec_module(blinkstick_monitor)


class TestColorConstants:
    """Tests for color constant definitions."""

    def test_green_color(self):
        """Test COLOR_GREEN is defined correctly."""
        assert blinkstick_monitor.COLOR_GREEN == (0, 64, 0)

    def test_red_color(self):
        """Test COLOR_RED is defined correctly."""
        assert blinkstick_monitor.COLOR_RED == (64, 0, 0)

    def test_yellow_color(self):
        """Test COLOR_YELLOW is defined correctly."""
        assert blinkstick_monitor.COLOR_YELLOW == (64, 40, 0)

    def test_blue_color(self):
        """Test COLOR_BLUE is defined correctly."""
        assert blinkstick_monitor.COLOR_BLUE == (0, 0, 64)

    def test_off_color(self):
        """Test COLOR_OFF is defined correctly."""
        assert blinkstick_monitor.COLOR_OFF == (0, 0, 0)


class TestDefaultConfiguration:
    """Tests for DEFAULT_CONFIG dictionary."""

    def test_default_config_exists(self):
        """Test DEFAULT_CONFIG is defined."""
        assert blinkstick_monitor.DEFAULT_CONFIG is not None

    def test_default_config_has_required_keys(self):
        """Test DEFAULT_CONFIG has all required keys."""
        required_keys = [
            'check_interval',
            'disk_warn_percent',
            'load_warn_multiplier',
            'boot_delay',
            'monitor_docker',
            'expected_containers',
            'expected_block_devices',
            'expected_mounts',
            'monitor_services',
            'expected_services',
            'container_blacklist_patterns',
            'mount_blacklist_patterns',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
            'led_count'
        ]
        for key in required_keys:
            assert key in blinkstick_monitor.DEFAULT_CONFIG, f"Missing key: {key}"

    def test_default_check_interval(self):
        """Test default check interval is 10."""
        assert blinkstick_monitor.DEFAULT_CONFIG['check_interval'] == 10

    def test_default_disk_warn_percent(self):
        """Test default disk warning percent is 85."""
        assert blinkstick_monitor.DEFAULT_CONFIG['disk_warn_percent'] == 85

    def test_default_load_warn_multiplier(self):
        """Test default load warning multiplier is 2.0."""
        assert blinkstick_monitor.DEFAULT_CONFIG['load_warn_multiplier'] == 2.0

    def test_default_boot_delay(self):
        """Test default boot delay is 30."""
        assert blinkstick_monitor.DEFAULT_CONFIG['boot_delay'] == 30

    def test_default_quiet_hours_enabled(self):
        """Test quiet hours enabled defaults to True."""
        assert blinkstick_monitor.DEFAULT_CONFIG['quiet_hours_enabled'] is True

    def test_default_quiet_hours_time_range(self):
        """Test default quiet hours is 23:00-07:00."""
        assert blinkstick_monitor.DEFAULT_CONFIG['quiet_hours_start'] == '23:00'
        assert blinkstick_monitor.DEFAULT_CONFIG['quiet_hours_end'] == '07:00'


class TestBlacklistFunction:
    """Tests for is_blacklisted function."""

    def test_exact_match(self):
        """Test exact match in blacklist."""
        assert blinkstick_monitor.is_blacklisted('mycontainer', ['mycontainer']) is True

    def test_wildcard_match(self):
        """Test wildcard pattern match."""
        assert blinkstick_monitor.is_blacklisted('sandbox-dev-01', ['sandbox-*']) is True

    def test_wildcard_no_match(self):
        """Test wildcard pattern does not match."""
        assert blinkstick_monitor.is_blacklisted('production-app', ['sandbox-*']) is False

    def test_multiple_patterns(self):
        """Test multiple blacklist patterns."""
        patterns = ['app-*', 'service-*', 'test-*']
        assert blinkstick_monitor.is_blacklisted('test-worker', patterns) is True
        assert blinkstick_monitor.is_blacklisted('app-server', patterns) is True
        assert blinkstick_monitor.is_blacklisted('prod-app', patterns) is False

    def test_no_blacklist(self):
        """Test no blacklist pattern matches."""
        assert blinkstick_monitor.is_blacklisted('anycontainer', []) is False


class TestQuietHoursFunction:
    """Tests for is_quiet_hours function."""

    def test_quiet_hours_disabled(self):
        """Test quiet hours returns False when disabled."""
        config = {'quiet_hours_enabled': False}
        # When quiet hours is disabled, datetime is not used
        assert blinkstick_monitor.is_quiet_hours(config) is False

    def test_outside_quiet_hours(self):
        """Test quiet hours returns False outside time window."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }
        # Save original datetime
        import datetime as dt_module
        original_datetime = blinkstick_monitor.datetime
        try:
            # Create a mock datetime class
            mock_datetime_class = mock.MagicMock()
            mock_dt_instance = mock.MagicMock()
            mock_dt_instance.strftime.return_value = '12:00'
            mock_datetime_class.now.return_value = mock_dt_instance
            # Patch the datetime module attribute
            blinkstick_monitor.datetime = mock_datetime_class
            assert blinkstick_monitor.is_quiet_hours(config) is False
        finally:
            # Restore original datetime
            blinkstick_monitor.datetime = original_datetime

    def test_inside_quiet_hours(self):
        """Test quiet hours returns True inside time window."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }
        import datetime as dt_module
        original_datetime = blinkstick_monitor.datetime
        try:
            mock_datetime_class = mock.MagicMock()
            mock_dt_instance = mock.MagicMock()
            mock_dt_instance.strftime.return_value = '02:00'
            mock_datetime_class.now.return_value = mock_dt_instance
            blinkstick_monitor.datetime = mock_datetime_class
            assert blinkstick_monitor.is_quiet_hours(config) is True
        finally:
            blinkstick_monitor.datetime = original_datetime

    def test_overnight_span(self):
        """Test overnight quiet hours span (23:00 -> 07:00)."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }
        import datetime as dt_module
        original_datetime = blinkstick_monitor.datetime
        try:
            # Test at 23:30 (just after start)
            mock_datetime_class1 = mock.MagicMock()
            mock_dt1 = mock.MagicMock()
            mock_dt1.strftime.return_value = '23:30'
            mock_datetime_class1.now.return_value = mock_dt1
            blinkstick_monitor.datetime = mock_datetime_class1
            assert blinkstick_monitor.is_quiet_hours(config) is True
            # Test at 05:00 (just before end)
            mock_datetime_class2 = mock.MagicMock()
            mock_dt2 = mock.MagicMock()
            mock_dt2.strftime.return_value = '05:00'
            mock_datetime_class2.now.return_value = mock_dt2
            blinkstick_monitor.datetime = mock_datetime_class2
            assert blinkstick_monitor.is_quiet_hours(config) is True
            # Test at 12:00 (outside overnight span)
            mock_datetime_class3 = mock.MagicMock()
            mock_dt3 = mock.MagicMock()
            mock_dt3.strftime.return_value = '12:00'
            mock_datetime_class3.now.return_value = mock_dt3
            blinkstick_monitor.datetime = mock_datetime_class3
            assert blinkstick_monitor.is_quiet_hours(config) is False
        finally:
            blinkstick_monitor.datetime = original_datetime

    def test_exception_returns_false(self):
        """Test that exceptions in is_quiet_hours return False."""
        config = {'quiet_hours_enabled': True}
        import datetime as dt_module
        original_datetime = blinkstick_monitor.datetime
        try:
            mock_datetime_class = mock.MagicMock()
            mock_dt_instance = mock.MagicMock()
            mock_dt_instance.strftime.side_effect = Exception("Test error")
            mock_datetime_class.now.return_value = mock_dt_instance
            blinkstick_monitor.datetime = mock_datetime_class
            assert blinkstick_monitor.is_quiet_hours(config) is False
        finally:
            blinkstick_monitor.datetime = original_datetime


class TestConfigMerge:
    """Tests for configuration merging functionality."""

    def test_load_or_create_config_with_existing(self):
        """Test loading existing config preserves user settings."""
        with mock.patch('builtins.open') as mock_open:
            import json
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                'quiet_hours_enabled': True,
                'quiet_hours_start': '22:00',
                'check_interval': 30
            })
            mock_open.return_value.__enter__.return_value.__iter__.return_value = []
            config = blinkstick_monitor.load_config()
            assert config is not None
            assert config['quiet_hours_enabled'] is True
            assert config['quiet_hours_start'] == '22:00'
            assert config['check_interval'] == 30
            # Defaults should be applied to missing keys
            assert config['led_count'] == blinkstick_monitor.DEFAULT_CONFIG['led_count']

    def test_load_config_returns_none_when_file_missing(self):
        """Test load_config returns None when config file missing."""
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            assert blinkstick_monitor.load_config() is None


class TestLoadOrCreateConfig:
    """Tests for load_or_create_config function."""

    def test_load_config_exists(self):
        """Test load_or_create_config returns loaded config."""
        with mock.patch.object(blinkstick_monitor, 'load_config') as mock_load:
            mock_load.return_value = {'test': 'config'}
            result = blinkstick_monitor.load_or_create_config()
            assert result == {'test': 'config'}

    def test_load_config_none_creates_default(self):
        """Test load_or_create_config creates config when load returns None."""
        with mock.patch.object(blinkstick_monitor, 'load_config') as mock_load:
            mock_load.return_value = None
            with mock.patch.object(blinkstick_monitor, 'detect_config') as mock_detect:
                mock_detect.return_value = {'auto': 'detected'}
                with mock.patch.object(blinkstick_monitor, 'save_config'):
                    with mock.patch.object(blinkstick_monitor, 'print_config'):
                        result = blinkstick_monitor.load_or_create_config()
                        assert result == {'auto': 'detected'}


class TestSignalHandler:
    """Tests for signal handling functionality."""

    def test_request_reload_sets_flag(self):
        """Test request_reload function sets global flag."""
        # Reset flag
        blinkstick_monitor._reload_requested = False
        # Trigger reload
        blinkstick_monitor.request_reload(1, None)
        assert blinkstick_monitor._reload_requested is True
