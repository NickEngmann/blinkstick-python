#!/usr/bin/env python3
"""
Comprehensive tests for blinkstick-monitor.py
Tests configuration parsing, health check logic (mocked), and color mapping utilities.
"""

import json
import os
import sys
from datetime import datetime
from unittest import mock

import pytest

# Import the module functions being tested
# Note: blinkstick-monitor.py has a hyphen, so we need to import it specially
import importlib.util
spec = importlib.util.spec_from_file_location("blinkstick_monitor", "blinkstick-monitor.py")
blinkstick_monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blinkstick_monitor)

# Expose all the functions for testing
COLOR_GREEN = blinkstick_monitor.COLOR_GREEN
COLOR_RED = blinkstick_monitor.COLOR_RED
COLOR_YELLOW = blinkstick_monitor.COLOR_YELLOW
COLOR_BLUE = blinkstick_monitor.COLOR_BLUE
COLOR_OFF = blinkstick_monitor.COLOR_OFF
DEFAULT_CONFIG = blinkstick_monitor.DEFAULT_CONFIG
is_blacklisted = blinkstick_monitor.is_blacklisted
is_quiet_hours = blinkstick_monitor.is_quiet_hours
determine_color = blinkstick_monitor.determine_color
run = blinkstick_monitor.run
check_docker = blinkstick_monitor.check_docker
check_services = blinkstick_monitor.check_services
check_block_devices = blinkstick_monitor.check_block_devices
check_mounts = blinkstick_monitor.check_mounts
check_disk_usage = blinkstick_monitor.check_disk_usage
check_load = blinkstick_monitor.check_load
load_config = blinkstick_monitor.load_config
detect_user_services = blinkstick_monitor.detect_user_services
run_all_checks = blinkstick_monitor.run_all_checks

# Test module path for mocking
TEST_MODULE = 'tests.test_blinkstick_monitor'


# ============================================================================
# Color definitions tests
# ============================================================================

class TestColorDefinitions:
    """Test that color constants are defined correctly."""

    def test_green_color(self):
        """Test GREEN color is (0, 64, 0)."""
        assert COLOR_GREEN == (0, 64, 0)

    def test_red_color(self):
        """Test RED color is (64, 0, 0)."""
        assert COLOR_RED == (64, 0, 0)

    def test_yellow_color(self):
        """Test YELLOW color is (64, 40, 0)."""
        assert COLOR_YELLOW == (64, 40, 0)

    def test_blue_color(self):
        """Test BLUE color is (0, 0, 64)."""
        assert COLOR_BLUE == (0, 0, 64)

    def test_off_color(self):
        """Test OFF color is (0, 0, 0)."""
        assert COLOR_OFF == (0, 0, 0)


# ============================================================================
# Default configuration tests
# ============================================================================

class TestDefaultConfiguration:
    """Test that DEFAULT_CONFIG has all required keys."""

    def test_default_config_exists(self):
        """Test that DEFAULT_CONFIG is a dictionary."""
        assert isinstance(DEFAULT_CONFIG, dict)

    def test_default_config_has_required_keys(self):
        """Test that DEFAULT_CONFIG has all required keys."""
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
        """Test that DEFAULT_CONFIG has expected default values."""
        assert DEFAULT_CONFIG['check_interval'] == 10
        assert DEFAULT_CONFIG['disk_warn_percent'] == 85
        assert DEFAULT_CONFIG['load_warn_multiplier'] == 2.0
        assert DEFAULT_CONFIG['boot_delay'] == 30
        assert DEFAULT_CONFIG['quiet_hours_enabled'] is True
        assert DEFAULT_CONFIG['quiet_hours_start'] == '23:00'
        assert DEFAULT_CONFIG['quiet_hours_end'] == '07:00'
        assert DEFAULT_CONFIG['led_count'] == 2


# ============================================================================
# Run function tests
# ============================================================================

class TestRunFunction:
    """Test the run() function for subprocess execution."""

    def test_run_success(self):
        """Test run() returns output and 0 for successful command."""
        output, rc = run(['echo', 'hello'])
        assert rc == 0
        assert output == 'hello'

    def test_run_not_found(self):
        """Test run() returns error code 127 when command not found."""
        output, rc = run(['nonexistent_command_xyz123'])
        assert rc == 127
        assert output == ''

    def test_run_timeout(self):
        """Test run() handles timeout gracefully."""
        output, rc = run(['sleep', '2'], timeout=1)
        assert rc == 1
        assert 'timed out' in output.lower()


# ============================================================================
# Blacklist function tests
# ============================================================================

class TestBlacklistFunction:
    """Test is_blacklisted() function with glob patterns."""

    def test_exact_match(self):
        """Test exact match with pattern."""
        assert is_blacklisted('my-container', ['my-container']) is True

    def test_wildcard_match(self):
        """Test wildcard pattern matching."""
        assert is_blacklisted('lotus-sandbox-abc123', ['lotus-sandbox-*']) is True
        assert is_blacklisted('lotus-sandbox-xyz', ['lotus-sandbox-*']) is True

    def test_no_match(self):
        """Test when name doesn't match any pattern."""
        assert is_blacklisted('other-container', ['lotus-sandbox-*']) is False
        assert is_blacklisted('different', ['my-pattern*']) is False

    def test_multiple_patterns(self):
        """Test with multiple blacklist patterns."""
        patterns = ['pattern1-*', 'pattern2-*', 'specific-name']
        assert is_blacklisted('pattern1-abc', patterns) is True
        assert is_blacklisted('pattern2-xyz', patterns) is True
        assert is_blacklisted('specific-name', patterns) is True
        assert is_blacklisted('other', patterns) is False


# ============================================================================
# Quiet hours function tests
# ============================================================================

class TestQuietHoursFunction:
    """Test is_quiet_hours() function."""

    def test_quiet_hours_disabled(self):
        """Test when quiet hours are disabled."""
        config = {'quiet_hours_enabled': False}
        assert is_quiet_hours(config) is False

    @mock.patch.object(blinkstick_monitor, 'datetime')
    def test_outside_window(self, mock_datetime_module):
        """Test when current time is outside quiet hours window."""
        mock_now_obj = mock_datetime_module.now.return_value
        mock_now_obj.strftime.return_value = '12:00'
        
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
        }
        assert is_quiet_hours(config) is False

    @mock.patch.object(blinkstick_monitor, 'datetime')
    def test_inside_window(self, mock_datetime_module):
        """Test when current time is inside quiet hours window."""
        mock_now_obj = mock_datetime_module.now.return_value
        mock_now_obj.strftime.return_value = '02:00'
        
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
        }
        assert is_quiet_hours(config) is True

    @mock.patch.object(blinkstick_monitor, 'datetime')
    def test_overnight_span_after_start(self, mock_datetime_module):
        """Test overnight quiet hours span - just after start (11 PM)."""
        mock_now_obj = mock_datetime_module.now.return_value
        mock_now_obj.strftime.return_value = '23:30'
        
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
        }
        assert is_quiet_hours(config) is True

    @mock.patch.object(blinkstick_monitor, 'datetime')
    def test_overnight_span_before_end(self, mock_datetime_module):
        """Test overnight quiet hours span - just before end (6 AM)."""
        mock_now_obj = mock_datetime_module.now.return_value
        mock_now_obj.strftime.return_value = '06:00'
        
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
        }
        assert is_quiet_hours(config) is True


# ============================================================================
# Determine color function tests
# ============================================================================

class TestDetermineColorFunction:
    """Test determine_color() function."""

    def test_no_issues(self):
        """Test when there are no issues - should return GREEN."""
        issues = []
        color, label = determine_color(issues)
        assert color == COLOR_GREEN
        assert label == 'GREEN'

    def test_warnings_only(self):
        """Test when there are only warnings - should return YELLOW."""
        issues = [
            ('warning', 'Disk /data at 90%'),
            ('warning', 'High load: 8.5'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_YELLOW
        assert label == 'YELLOW'

    def test_critical_issues(self):
        """Test when there are critical issues - should return RED."""
        issues = [
            ('critical', 'Container docker-compose down'),
            ('warning', 'Disk /home at 85%'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_RED
        assert label == 'RED'

    def test_critical_overrides_warning(self):
        """Test that critical issues take precedence over warnings."""
        issues = [
            ('warning', 'Low disk space'),
            ('critical', 'Service down'),
            ('warning', 'High load'),
        ]
        color, label = determine_color(issues)
        assert color == COLOR_RED
        assert label == 'RED'


# ============================================================================
# Health check function tests (mocked)
# ============================================================================

class TestHealthCheckFunctions:
    """Test health check functions with mocked subprocess calls."""

    def test_check_docker_no_monitoring(self):
        """Test check_docker when monitoring is disabled."""
        config = {'monitor_docker': False}
        issues = check_docker(config)
        assert issues == []

    def test_check_docker_daemon_unreachable(self):
        """Test check_docker when Docker daemon is unreachable."""
        config = {'monitor_docker': True, 'expected_containers': ['web']}
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)
            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Cannot reach Docker daemon' in issues[0][1]

    def test_check_docker_container_down(self):
        """Test check_docker detects container is down."""
        config = {'monitor_docker': True, 'expected_containers': ['web', 'db']}
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            # web is unhealthy, db exited
            mock_run.return_value = (
                'web\tUp 2 hours (unhealthy)\ndb\tExited 1 day ago',
                0
            )
            issues = check_docker(config)
            assert len(issues) == 2
            assert any('unhealthy' in i[1].lower() for i in issues)
            assert any('Exited' in i[1] for i in issues)

    def test_check_docker_all_healthy(self):
        """Test check_docker when all containers are healthy."""
        config = {'monitor_docker': True, 'expected_containers': ['web', 'db']}
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = (
                'web\tUp 2 hours\ndb\tUp 5 hours',
                0
            )
            issues = check_docker(config)
            assert issues == []

    def test_check_services_no_monitoring(self):
        """Test check_services when monitoring is disabled."""
        config = {'monitor_services': False}
        issues = check_services(config)
        assert issues == []

    def test_check_service_down(self):
        """Test check_services detects service is down."""
        config = {
            'monitor_services': True,
            'expected_services': ['web.service', 'api.service'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == 'systemctl' and 'is-active' in cmd:
                    if 'api.service' in cmd:
                        return ('', 1)
                    return ('active', 0)
                elif cmd[0] == 'systemctl' and 'cat' in cmd:
                    return ('', 0)
                return ('', 0)
            
            mock_run.side_effect = run_side_effect
            issues = check_services(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'api.service' in issues[0][1]

    def test_check_block_devices_no_issues(self):
        """Test check_block_devices when all devices are present."""
        config = {
            'monitor_services': False,
            'expected_block_devices': ['sda', 'nvme0n1'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('sda\nnvme0n1\nsdb', 0)
            issues = check_block_devices(config)
            assert issues == []

    def test_check_block_device_missing(self):
        """Test check_block_devices detects missing device."""
        config = {
            'expected_block_devices': ['sda', 'nvme0n1'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('sda\nsdb', 0)
            issues = check_block_devices(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'nvme0n1' in issues[0][1]

    def test_check_mounts_no_issues(self):
        """Test check_mounts when all mounts are present."""
        config = {
            'expected_mounts': ['/', '/data', '/backup'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('/\n/data\n/backup', 0)
            issues = check_mounts(config)
            assert issues == []

    def test_check_mount_missing(self):
        """Test check_mounts detects missing mount."""
        config = {
            'expected_mounts': ['/', '/data', '/backup'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('/\n/data\n/home', 0)
            issues = check_mounts(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert '/backup' in issues[0][1]

    def test_check_disk_usage_below_threshold(self):
        """Test check_disk_usage when disk usage is below warning threshold."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': [],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = (
                '75  /\n60  /data\n50  /home',
                0
            )
            issues = check_disk_usage(config)
            assert issues == []

    def test_check_disk_usage_above_threshold(self):
        """Test check_disk_usage detects high disk usage."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': [],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = (
                '75  /\n90  /data\n50  /home',
                0
            )
            issues = check_disk_usage(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert '/data' in issues[0][1]

    def test_check_disk_usage_blacklisted(self):
        """Test check_disk_usage skips blacklisted mounts."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': ['/mnt/nvme*'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = (
                '75  /\n90  /mnt/nvme0\n50  /home',
                0
            )
            issues = check_disk_usage(config)
            assert issues == []

    def test_check_load_below_threshold(self):
        """Test check_load when load is below threshold."""
        config = {
            'load_warn_multiplier': 2.0,
        }
        
        with mock.patch('os.getloadavg') as mock_load:
            with mock.patch('os.cpu_count', return_value=4):
                mock_load.return_value = (1.5, 2.0, 1.8)
                issues = check_load(config)
                assert issues == []

    def test_check_load_above_threshold(self):
        """Test check_load detects high load."""
        config = {
            'load_warn_multiplier': 2.0,
        }
        
        with mock.patch('os.getloadavg') as mock_load:
            with mock.patch('os.cpu_count', return_value=4):
                # 4 CPUs, threshold = 8.0, load 10.0 is above
                mock_load.return_value = (10.0, 9.5, 9.0)
                issues = check_load(config)
                assert len(issues) == 1
                assert issues[0][0] == 'warning'
                assert 'High load' in issues[0][1]

    def test_check_load_no_os_error(self):
        """Test check_load handles OSError gracefully."""
        config = {}
        
        with mock.patch('os.getloadavg') as mock_load:
            mock_load.side_effect = OSError("No data available")
            issues = check_load(config)
            assert issues == []


class TestRunAllChecks:
    """Test run_all_checks() function."""

    def test_run_all_checks_no_issues(self):
        """Test run_all_checks returns empty list when all healthy."""
        config = {
            'monitor_docker': False,
            'monitor_services': False,
            'expected_block_devices': [],
            'expected_mounts': [],
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0,
        }
        
        issues = run_all_checks(config)
        assert issues == []

    def test_run_all_checks_with_issues(self):
        """Test run_all_checks aggregates issues from all checks."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['web'],
        }
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)  # Docker unreachable
            issues = run_all_checks(config)
            assert len(issues) >= 1
            assert any('critical' in i[0] for i in issues)


# ============================================================================
# Detect user services tests
# ============================================================================

class TestDetectUserServices:
    """Test detect_user_services() function."""

    def test_detect_user_services_no_services(self):
        """Test when no user services exist."""
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 0)
            services = detect_user_services()
            assert services == []

    def test_detect_user_services_excludes_timers_and_cron(self):
        """Test that timers and cron services are excluded."""
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == 'find':
                    return (
                        '/etc/systemd/system/my-webapp.service\n'
                        '/etc/systemd/system/my-timer.timer\n'
                        '/etc/systemd/system/cron.service\n'
                        '/etc/systemd-system/blinkstick-monitor.service',
                        0
                    )
                elif cmd[0] == 'systemctl' and cmd[1] == 'is-active':
                    for unit in ['my-webapp.service', 'my-timer.timer', 'cron.service', 'blinkstick-monitor.service']:
                        if unit in cmd:
                            if unit == 'my-webapp.service':
                                return ('active', 0)
                            return ('inactive', 1)
                return ('', 0)

            mock_run.side_effect = run_side_effect
            services = detect_user_services()
            assert services == ['my-webapp.service']

    def test_detect_user_services_excludes_inactive(self):
        """Test that inactive services are not included."""
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == 'find':
                    return '/etc/systemd/system/my-webapp.service\n/etc/systemd/system/my-api.service', 0
                elif cmd[0] == 'systemctl' and cmd[1] == 'is-active':
                    for unit in ['my-webapp.service', 'my-api.service']:
                        if unit in cmd:
                            if unit == 'my-webapp.service':
                                return ('active', 0)
                            return ('inactive', 1)  # my-api is not active
                return ('', 0)

            mock_run.side_effect = run_side_effect
            services = detect_user_services()
            assert services == ['my-webapp.service']


# ============================================================================
# Load config tests
# ============================================================================

class TestLoadConfig:
    """Test load_config() function."""

    def test_load_config_file_not_found(self, tmp_path):
        """Test when config file doesn't exist."""
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            config = load_config()
            assert config is None

    def test_load_config_invalid_json(self, tmp_path):
        """Test when config file has invalid JSON."""
        config_path = tmp_path / 'blinkstick-monitor.conf'
        config_path.write_text('not valid json {')
        
        with mock.patch('os.path.exists', return_value=True):
            with mock.patch('builtins.open', mock.mock_open(read_data='not valid json {')):
                config = load_config()
                assert config is None


# ============================================================================
# Integration tests
# ============================================================================

class TestIntegration:
    """Integration tests for combined functionality."""

    def test_full_workflow_no_issues(self):
        """Test full workflow with no issues - should return GREEN."""
        config = {
            'monitor_docker': False,
            'monitor_services': False,
            'expected_block_devices': [],
            'expected_mounts': [],
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0,
        }
        
        issues = run_all_checks(config)
        color, label = determine_color(issues)
        
        assert issues == []
        assert color == COLOR_GREEN
        assert label == 'GREEN'

    def test_full_workflow_with_warnings(self):
        """Test full workflow with warnings - should return YELLOW."""
        config = {
            'load_warn_multiplier': 2.0,
        }
        
        with mock.patch('os.getloadavg') as mock_load:
            with mock.patch('os.cpu_count', return_value=1):
                mock_load.return_value = (3.0, 2.5, 2.0)
                
                issues = check_load(config)
                assert len(issues) == 1
                assert issues[0][0] == 'warning'
                
                color, label = determine_color(issues)
                assert color == COLOR_YELLOW
                assert label == 'YELLOW'

    def test_full_workflow_with_critical(self):
        """Test full workflow with critical issues - should return RED."""
        config = {'monitor_docker': True, 'expected_containers': ['web']}
        
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)  # Docker daemon unreachable
            
            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            
            color, label = determine_color(issues)
            assert color == COLOR_RED
            assert label == 'RED'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
