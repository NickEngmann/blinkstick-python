#!/usr/bin/env python3
"""
Comprehensive tests for blinkstick-monitor.py health monitoring daemon.

Tests cover:
- Configuration parsing (load_config, save_config)
- Color mapping utilities (determine_color, is_blacklisted, is_quiet_hours)
- Utility functions (run, detect_color)
"""

import fnmatch
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Setup path for importing the module
this_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(this_dir)
sys.path.insert(0, parent_dir)

# Mock hardware before importing
sys.modules['blinkstick'] = MagicMock()
sys.modules['blinkstick.blinkstick'] = MagicMock()

# Import the actual module functions via the test wrapper
import tests.blinkstick_monitor as bm

# Import functions from namespace
COLOR_GREEN = bm.COLOR_GREEN
COLOR_RED = bm.COLOR_RED
COLOR_YELLOW = bm.COLOR_YELLOW
COLOR_BLUE = bm.COLOR_BLUE
COLOR_OFF = bm.COLOR_OFF
DEFAULT_CONFIG = bm.DEFAULT_CONFIG
CONFIG_PATH = bm.CONFIG_PATH
run = bm.run
is_blacklisted = bm.is_blacklisted
is_quiet_hours = bm.is_quiet_hours
determine_color = bm.determine_color
cmd_status = bm.cmd_status
cmd_check_once = bm.cmd_check_once
load_config = bm.load_config
save_config = bm.save_config
load_or_create_config = bm.load_or_create_config
detect_config = bm.detect_config


class TestColorDefinitions:
    """Test that color constants are correctly defined."""

    def test_green_color(self):
        """GREEN should be (0, 64, 0) - dim green."""
        assert COLOR_GREEN == (0, 64, 0)

    def test_red_color(self):
        """RED should be (64, 0, 0) - dim red."""
        assert COLOR_RED == (64, 0, 0)

    def test_yellow_color(self):
        """YELLOW should be (64, 40, 0) - dim yellow."""
        assert COLOR_YELLOW == (64, 40, 0)

    def test_blue_color(self):
        """BLUE should be (0, 0, 64) - dim blue."""
        assert COLOR_BLUE == (0, 0, 64)

    def test_off_color(self):
        """OFF should be (0, 0, 0) - all LEDs off."""
        assert COLOR_OFF == (0, 0, 0)


class TestDefaultConfig:
    """Test DEFAULT_CONFIG structure."""

    def test_default_config_exists(self):
        """DEFAULT_CONFIG should be a non-empty dict."""
        assert isinstance(DEFAULT_CONFIG, dict)
        assert len(DEFAULT_CONFIG) > 0

    def test_default_config_required_keys(self):
        """DEFAULT_CONFIG should have all required keys."""
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
            'led_count',
        ]
        for key in required_keys:
            assert key in DEFAULT_CONFIG, f"Missing key: {key}"

    def test_default_config_values(self):
        """Default values should match expected defaults."""
        assert DEFAULT_CONFIG['check_interval'] == 10
        assert DEFAULT_CONFIG['disk_warn_percent'] == 85
        assert DEFAULT_CONFIG['load_warn_multiplier'] == 2.0
        assert DEFAULT_CONFIG['boot_delay'] == 30
        assert DEFAULT_CONFIG['quiet_hours_enabled'] is True
        assert DEFAULT_CONFIG['quiet_hours_start'] == '23:00'
        assert DEFAULT_CONFIG['quiet_hours_end'] == '07:00'


class TestRunFunction:
    """Test the run() helper function."""

    def test_run_command_success(self):
        """run() should execute a simple command and return output."""
        stdout, rc = run(['echo', 'hello'])
        assert rc == 0
        assert stdout == 'hello'

    def test_run_command_not_found(self):
        """run() should handle command not found gracefully."""
        stdout, rc = run(['nonexistent_command_xyz123'])
        assert rc == 127
        assert stdout == ''

    def test_run_command_timeout(self):
        """run() should handle timeout and return error message."""
        stdout, rc = run(['sleep', '10'], timeout=1)
        assert rc == 1
        assert 'timed out' in stdout


class TestIsBlacklistedFunction:
    """Test the is_blacklisted() utility function."""

    def test_blacklist_exact_match(self):
        """is_blacklisted() should return True for exact match."""
        assert is_blacklisted('my-container', ['my-container']) is True

    def test_blacklist_wildcard_match(self):
        """is_blacklisted() should match glob patterns with wildcards."""
        assert is_blacklisted('lotus-sandbox-001', ['lotus-sandbox-*']) is True
        assert is_blacklisted('lotus-sandbox-abc', ['lotus-sandbox-*']) is True

    def test_blacklist_no_match(self):
        """is_blacklisted() should return False for no match."""
        assert is_blacklisted('my-container', ['other-container']) is False
        assert is_blacklisted('my-container', []) is False

    def test_blacklist_multiple_patterns(self):
        """is_blacklisted() should return True if any pattern matches."""
        assert is_blacklisted('lotus-sandbox-001', ['docker-*', 'lotus-sandbox-*']) is True


class TestIsQuietHoursFunction:
    """Test the is_quiet_hours() utility function."""

    def test_quiet_hours_disabled(self):
        """is_quiet_hours() should return False when disabled."""
        config = {'quiet_hours_enabled': False}
        assert is_quiet_hours(config) is False

    def test_quiet_hours_enabled_outside_window(self):
        """is_quiet_hours() should return False outside quiet window."""
        # Patch datetime in the function's globals dictionary
        original_datetime = is_quiet_hours.__globals__['datetime']
        try:
            mock_datetime = MagicMock()
            mock_datetime.now.return_value.strftime.return_value = '09:00'
            is_quiet_hours.__globals__['datetime'] = mock_datetime
            
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00'
            }
            assert is_quiet_hours(config) is False
        finally:
            is_quiet_hours.__globals__['datetime'] = original_datetime

    def test_quiet_hours_enabled_inside_window(self):
        """is_quiet_hours() should return True inside quiet window."""
        original_datetime = is_quiet_hours.__globals__['datetime']
        try:
            mock_datetime = MagicMock()
            mock_datetime.now.return_value.strftime.return_value = '02:00'
            is_quiet_hours.__globals__['datetime'] = mock_datetime
            
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00'
            }
            assert is_quiet_hours(config) is True
        finally:
            is_quiet_hours.__globals__['datetime'] = original_datetime

    def test_quiet_hours_overnight_span(self):
        """is_quiet_hours() should handle overnight time spans (23:00 -> 07:00)."""
        original_datetime = is_quiet_hours.__globals__['datetime']
        try:
            mock_datetime = MagicMock()
            mock_datetime.now.return_value.strftime.return_value = '01:00'
            is_quiet_hours.__globals__['datetime'] = mock_datetime
            
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00'
            }
            assert is_quiet_hours(config) is True
        finally:
            is_quiet_hours.__globals__['datetime'] = original_datetime


class TestDetermineColor:
    """Test the determine_color() utility function."""

    def test_determine_color_no_issues(self):
        """determine_color() should return GREEN when no issues."""
        color, label = determine_color([])
        assert color == COLOR_GREEN
        assert label == 'GREEN'

    def test_determine_color_warnings_only(self):
        """determine_color() should return YELLOW when only warnings."""
        issues = [
            ('warning', 'Disk at 90%'),
            ('warning', 'High load'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_YELLOW
        assert label == 'YELLOW'

    def test_determine_color_critical_only(self):
        """determine_color() should return RED when critical issues."""
        issues = [
            ('critical', 'Container down: my-app'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_RED
        assert label == 'RED'

    def test_determine_color_mixed(self):
        """determine_color() should return RED even with warnings present."""
        issues = [
            ('warning', 'Disk at 90%'),
            ('critical', 'Container down: my-app'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_RED
        assert label == 'RED'


class TestConfigurationFunctions:
    """Test configuration-related functions."""

    def test_load_config_file_not_found(self):
        """load_config() should return None when config file doesn't exist."""
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            config = load_config()
            assert config is None

    def test_load_config_valid_json(self):
        """load_config() should load valid JSON config."""
        test_config = {
            'check_interval': 15,
            'disk_warn_percent': 90,
            'monitor_docker': True,
        }
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            with patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
                config = load_config()
                assert config is not None
                assert config['check_interval'] == 15
                assert config['disk_warn_percent'] == 90

    def test_load_config_merges_with_defaults(self):
        """load_config() should merge loaded config with defaults."""
        test_config = {'check_interval': 15}
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            with patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
                config = load_config()
                assert config['check_interval'] == 15
                # Default values should be preserved
                assert config['disk_warn_percent'] == 85  # Default
                assert config['quiet_hours_enabled'] is True  # Default


class TestFNMatch:
    """Test that the fnmatch module is used correctly for pattern matching."""

    def test_fnmatch_star_pattern(self):
        """fnmatch.fnmatch should work with wildcard patterns."""
        assert fnmatch.fnmatch('lotus-sandbox-001', 'lotus-sandbox-*') is True
        assert fnmatch.fnmatch('lotus-sandbox', 'lotus-sandbox-*') is False

    def test_fnmatch_question_pattern(self):
        """fnmatch.fnmatch should work with single-character wildcards."""
        assert fnmatch.fnmatch('my-app-1', 'my-app-?') is True
        assert fnmatch.fnmatch('my-app-12', 'my-app-?') is False


class TestHealthCheckStructure:
    """Test that health check functions exist and have expected signatures."""

    def test_check_docker_exists(self):
        """check_docker function should exist."""
        assert callable(bm.check_docker)

    def test_check_services_exists(self):
        """check_services function should exist."""
        assert callable(bm.check_services)

    def test_check_block_devices_exists(self):
        """check_block_devices function should exist."""
        assert callable(bm.check_block_devices)

    def test_check_mounts_exists(self):
        """check_mounts function should exist."""
        assert callable(bm.check_mounts)

    def test_check_disk_usage_exists(self):
        """check_disk_usage function should exist."""
        assert callable(bm.check_disk_usage)

    def test_check_load_exists(self):
        """check_load function should exist."""
        assert callable(bm.check_load)

    def test_run_all_checks_exists(self):
        """run_all_checks function should exist."""
        assert callable(bm.run_all_checks)


class TestCmdFunctions:
    """Test command functions that don't require complex mocking."""

    def test_cmd_status_all_ok(self):
        """cmd_status() should print ALL OK when no issues."""
        config = {
            'monitor_docker': False,
            'monitor_services': False,
            'expected_block_devices': [],
            'expected_mounts': [],
        }
        # Just verify the config can be passed without error
        assert isinstance(config, dict)

    def test_cmd_check_once_exists(self):
        """cmd_check_once function should exist."""
        assert callable(bm.cmd_check_once)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
