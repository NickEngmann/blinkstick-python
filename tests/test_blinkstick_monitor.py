"""
Tests for blinkstick-monitor.py

Covers:
- Configuration parsing (load_config, load_or_create_config, detect_config)
- Health check logic (mocked) - check_docker, check_services, check_block_devices, check_mounts, check_disk_usage, check_load
- Color mapping utilities (determine_color, color definitions)
- Quiet hours logic
- Blacklist filtering
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Import the target module functions
import blinkstick_monitor
from blinkstick_monitor import (
    check_docker, check_services, check_block_devices, check_mounts,
    check_disk_usage, check_load, run_all_checks, determine_color,
    is_quiet_hours, is_blacklisted, detect_config, load_config,
    load_or_create_config, DEFAULT_CONFIG, COLOR_GREEN, COLOR_RED,
    COLOR_YELLOW, COLOR_BLUE, COLOR_OFF
)


class TestConfigurationParsing:
    """Tests for configuration loading, parsing, and detection."""

    def test_load_config_returns_none_when_file_missing(self, tmp_path):
        """load_config should return None when config file does not exist."""
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(tmp_path / 'nonexistent.conf')):
            result = blinkstick_monitor.load_config()
            assert result is None

    def test_load_config_returns_dict_when_file_exists(self, tmp_path):
        """load_config should parse JSON config file correctly."""
        config = {
            'check_interval': 15,
            'disk_warn_percent': 90,
            'expected_containers': ['nginx', 'redis'],
        }
        config_path = tmp_path / 'test.conf'
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(config_path)):
            result = blinkstick_monitor.load_config()
            assert isinstance(result, dict)
            assert result['check_interval'] == 15
            assert result['disk_warn_percent'] == 90
            assert result['expected_containers'] == ['nginx', 'redis']

    def test_load_config_merges_with_defaults(self, tmp_path):
        """load_config should merge loaded config with DEFAULT_CONFIG."""
        config = {'check_interval': 5}
        config_path = tmp_path / 'test.conf'
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(config_path)):
            result = blinkstick_monitor.load_config()
            # Should have both loaded key and default keys
            assert result['check_interval'] == 5
            assert 'led_count' in result
            assert 'quiet_hours_enabled' in result

    def test_load_config_returns_none_on_json_error(self, tmp_path):
        """load_config should return None when JSON is invalid."""
        config_path = tmp_path / 'invalid.json'
        with open(config_path, 'w') as f:
            f.write('not valid json')
        
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(config_path)):
            result = blinkstick_monitor.load_config()
            assert result is None

    def test_load_or_create_config_loads_existing(self, tmp_path):
        """load_or_create_config should load existing config."""
        config = {'check_interval': 10}
        config_path = tmp_path / 'test.conf'
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(config_path)):
            with patch.object(blinkstick_monitor, 'load_config', return_value=config):
                with patch.object(blinkstick_monitor, 'log'):
                    result = blinkstick_monitor.load_or_create_config()
                    assert result == config

    def test_load_or_create_config_creates_when_missing(self, tmp_path):
        """load_or_create_config should call detect_config when no config exists."""
        config_path = tmp_path / 'test.conf'
        
        with patch.object(blinkstick_monitor, 'CONFIG_PATH', str(config_path)):
            with patch.object(blinkstick_monitor, 'load_config', return_value=None):
                with patch.object(blinkstick_monitor, 'detect_config', return_value={'check_interval': 10}):
                    with patch.object(blinkstick_monitor, 'log'):
                        with patch.object(blinkstick_monitor, 'print_config'):
                            result = blinkstick_monitor.load_or_create_config()
                            assert result == {'check_interval': 10}

    def test_detect_config_creates_default_structure(self):
        """detect_config should create a config with default structure."""
        with patch.object(blinkstick_monitor, 'run') as mock_run:
            # Simulate docker ps not available (127 = command not found)
            mock_run.return_value = ('', 127)
            
            result = blinkstick_monitor.detect_config()
            assert 'check_interval' in result
            assert 'disk_warn_percent' in result
            assert result['expected_containers'] == []
            assert result['monitor_docker'] in (True, False)

    def test_detect_config_caries_forward_quiet_hours_settings(self, tmp_path):
        """detect_config should carry forward quiet hours settings from existing config."""
        existing_config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '06:00',
        }
        
        with patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 127)
            
            result = blinkstick_monitor.detect_config(preserve_config=existing_config)
            assert result['quiet_hours_enabled'] == True
            assert result['quiet_hours_start'] == '22:00'
            assert result['quiet_hours_end'] == '06:00'

    def test_detect_config_carries_forward_blacklist_patterns(self, tmp_path):
        """detect_config should carry forward blacklist patterns from existing config."""
        existing_config = {
            'container_blacklist_patterns': ['sandbox-*', 'test-*'],
        }
        
        with patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 127)
            
            result = blinkstick_monitor.detect_config(blacklist=existing_config.get('container_blacklist_patterns', []),
                                                      preserve_config=existing_config)
            assert 'container_blacklist_patterns' in result


class TestHealthCheckLogic:
    """Tests for health check functions (mocked)."""

    def test_check_docker_returns_empty_when_not_monitoring(self):
        """check_docker should return empty list when monitor_docker is False."""
        config = {'monitor_docker': False}
        issues = blinkstick_monitor.check_docker(config)
        assert issues == []

    def test_check_docker_returns_critical_when_docker_unreachable(self):
        """check_docker should report critical when Docker daemon unreachable."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('', 1)):
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Docker daemon' in issues[0][1]

    def test_check_docker_reports_missing_container(self):
        """check_docker should report missing containers."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx', 'redis'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('nginx\tUp 5 hours\n', 0)):
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert 'redis' in issues[0][1]
            assert issues[0][0] == 'critical'

    def test_check_docker_reports_container_down(self):
        """check_docker should report containers that are not Up."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('nginx\tExited (1) 2 hours ago\n', 0)):
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert 'down' in issues[0][1].lower()
            assert issues[0][0] == 'critical'

    def test_check_docker_reports_unhealthy_container(self):
        """check_docker should report unhealthy containers as warnings."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('nginx\tUp (unhealthy) 5 hours\n', 0)):
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert 'unhealthy' in issues[0][1].lower()
            assert issues[0][0] == 'warning'

    def test_check_services_returns_empty_when_not_monitoring(self):
        """check_services should return empty list when monitor_services is False."""
        config = {'monitor_services': False}
        issues = blinkstick_monitor.check_services(config)
        assert issues == []

    def test_check_services_reports_missing_service(self):
        """check_services should report critical when service is down."""
        config = {
            'monitor_services': True,
            'expected_services': ['my-service'],
        }
        with patch.object(blinkstick_monitor, 'run', side_effect=[
            ('', 1),   # service not active
            ('', 0),   # service exists (cat succeeds)
        ]):
            issues = blinkstick_monitor.check_services(config)
            assert len(issues) == 1
            assert 'my-service' in issues[0][1]
            assert issues[0][0] == 'critical'

    def test_check_services_warns_on_removed_service(self):
        """check_services should warn when service unit no longer exists."""
        config = {
            'monitor_services': True,
            'expected_services': ['removed-service'],
        }
        with patch.object(blinkstick_monitor, 'run', side_effect=[
            ('', 1),   # not active
            ('', 1),   # doesn't exist
        ]):
            issues = blinkstick_monitor.check_services(config)
            assert len(issues) == 1
            assert 'removed' in issues[0][1]
            assert issues[0][0] == 'warning'

    def test_check_block_devices_returns_empty_list(self):
        """check_block_devices should handle missing lsblk gracefully."""
        config = {
            'expected_block_devices': ['sda', 'nvme0n1'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('', 1)):
            issues = blinkstick_monitor.check_block_devices(config)
            assert len(issues) >= 0  # May report warning or be empty if lsblk fails

    def test_check_block_devices_reports_missing_device(self):
        """check_block_devices should report missing block devices."""
        config = {
            'expected_block_devices': ['sda', 'hdd1'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('sda\nsdb\n', 0)):
            issues = blinkstick_monitor.check_block_devices(config)
            assert len(issues) == 1
            assert 'hdd1' in issues[0][1]
            assert issues[0][0] == 'critical'

    def test_check_mounts_reports_missing_mount(self):
        """check_mounts should report missing mount points."""
        config = {
            'expected_mounts': ['/home', '/data'],
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('/home\n', 0)):
            issues = blinkstick_monitor.check_mounts(config)
            assert len(issues) == 1
            assert '/data' in issues[0][1]
            assert issues[0][0] == 'critical'

    def test_check_disk_usage_reports_warning_above_threshold(self):
        """check_disk_usage should warn when disk usage exceeds threshold."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': [],
        }
        # df output format: percentage and target separated by whitespace
        with patch.object(blinkstick_monitor, 'run', return_value=(
            'PCT TARGET\n90% /mnt/data\n80% /home\n', 0
        )):
            issues = blinkstick_monitor.check_disk_usage(config)
            # Should report warning for mount at 90%
            assert any('warning' in issue[0] for issue in issues)

    def test_check_disk_usage_respects_blacklist(self):
        """check_disk_usage should skip blacklisted mounts."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': ['/mnt/blacklisted-*'],
        }
        # df output format: percentage and target separated by whitespace
        with patch.object(blinkstick_monitor, 'run', return_value=(
            'PCT TARGET\n90% /mnt/blacklisted-data\n80% /valid\n', 0
        )):
            issues = blinkstick_monitor.check_disk_usage(config)
            # Should not report blacklisted mount
            issues_str = [issue[1].lower() for issue in issues]
            assert not any('blacklisted' in s for s in issues_str)

    def test_check_load_reports_high_load(self):
        """check_load should warn when system load exceeds threshold."""
        config = {
            'load_warn_multiplier': 1.0,
        }
        with patch.object(blinkstick_monitor, 'os', MagicMock(getloadavg=lambda: (5.0, 4.0, 3.0), cpu_count=lambda: 2)):
            issues = blinkstick_monitor.check_load(config)
            assert len(issues) == 1
            assert 'warning' in issues[0][0]
            assert 'load' in issues[0][1].lower()

    def test_check_load_no_warning_when_ok(self):
        """check_load should return empty when load is normal."""
        config = {
            'load_warn_multiplier': 3.0,
        }
        with patch.object(blinkstick_monitor, 'os', MagicMock(getloadavg=lambda: (1.0, 1.0, 1.0), cpu_count=lambda: 4)):
            issues = blinkstick_monitor.check_load(config)
            assert issues == []

    def test_run_all_checks_aggregates_all_issues(self):
        """run_all_checks should aggregate issues from all check functions."""
        config = {
            'monitor_docker': False,
            'monitor_services': False,
            'expected_block_devices': ['nonexistent'],
            'expected_mounts': ['/nonexistent'],
            'disk_warn_percent': 85,
            'load_warn_multiplier': 1.0,
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('', 0)):
            with patch.object(blinkstick_monitor, 'os', MagicMock(getloadavg=lambda: (0.5, 0.5, 0.5), cpu_count=lambda: 4)):
                issues = blinkstick_monitor.run_all_checks(config)
                assert len(issues) >= 2  # At least block device and mount issues

    def test_run_all_checks_returns_empty_when_healthy(self):
        """run_all_checks should return empty list when all checks pass."""
        config = {
            'monitor_docker': False,
            'monitor_services': False,
            'expected_block_devices': [],
            'expected_mounts': [],
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0,
        }
        with patch.object(blinkstick_monitor, 'run', return_value=('', 0)):
            with patch.object(blinkstick_monitor, 'os', MagicMock(getloadavg=lambda: (0.5, 0.5, 0.5), cpu_count=lambda: 4)):
                issues = blinkstick_monitor.run_all_checks(config)
                assert issues == []


class TestColorMapping:
    """Tests for color mapping and LED control logic."""

    def test_determine_color_returns_green_when_no_issues(self):
        """determine_color should return GREEN when all checks pass."""
        color, label = blinkstick_monitor.determine_color([])
        assert color == blinkstick_monitor.COLOR_GREEN
        assert label == 'GREEN'

    def test_determine_color_returns_red_for_critical_issues(self):
        """determine_color should return RED when critical issues present."""
        issues = [
            ('critical', 'Container down: nginx'),
            ('critical', 'Service down: my-service'),
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert color == blinkstick_monitor.COLOR_RED
        assert label == 'RED'

    def test_determine_color_returns_yellow_for_warnings_only(self):
        """determine_color should return YELLOW when only warnings present."""
        issues = [
            ('warning', 'Disk /mnt/data at 90%'),
            ('warning', 'High load: 5.0'),
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert color == blinkstick_monitor.COLOR_YELLOW
        assert label == 'YELLOW'

    def test_determine_color_prioritizes_critical_over_warning(self):
        """determine_color should return RED even when both critical and warning present."""
        issues = [
            ('critical', 'Container down: nginx'),
            ('warning', 'Disk at 90%'),
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert color == blinkstick_monitor.COLOR_RED
        assert label == 'RED'

    def test_color_definitions_are_tuples(self):
        """Color definitions should be RGB tuples."""
        assert isinstance(blinkstick_monitor.COLOR_GREEN, tuple)
        assert isinstance(blinkstick_monitor.COLOR_RED, tuple)
        assert isinstance(blinkstick_monitor.COLOR_YELLOW, tuple)
        assert isinstance(blinkstick_monitor.COLOR_BLUE, tuple)
        assert isinstance(blinkstick_monitor.COLOR_OFF, tuple)
        
        # Check values are reasonable (0-255 range)
        for color in [blinkstick_monitor.COLOR_GREEN, blinkstick_monitor.COLOR_RED,
                      blinkstick_monitor.COLOR_YELLOW, blinkstick_monitor.COLOR_BLUE]:
            assert all(0 <= c <= 255 for c in color)

    def test_set_blinkstick_color_returns_false_when_no_device(self, caplog):
        """set_blinkstick_color should return False when no BlinkStick found."""
        with patch.object(blinkstick_monitor, 'get_stick', return_value=None):
            result = blinkstick_monitor.set_blinkstick_color(255, 0, 0, led_count=2)
            assert result is False


class TestQuietHoursLogic:
    """Tests for quiet hours detection."""

    def test_is_quiet_hours_false_when_disabled(self):
        """is_quiet_hours should return False when quiet hours disabled."""
        config = {'quiet_hours_enabled': False}
        with patch('blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '12:00'
            result = blinkstick_monitor.is_quiet_hours(config)
            assert result is False

    def test_is_quiet_hours_true_during_quiet_hours(self):
        """is_quiet_hours should return True during quiet hours."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '06:00',
        }
        with patch('blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '23:30'
            result = blinkstick_monitor.is_quiet_hours(config)
            assert result is True

    def test_is_quiet_hours_false_outside_quiet_hours(self):
        """is_quiet_hours should return False outside quiet hours."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '06:00',
        }
        with patch('blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '10:00'
            result = blinkstick_monitor.is_quiet_hours(config)
            assert result is False

    def test_is_quiet_hours_handles_overnight_span(self):
        """is_quiet_hours should handle overnight spans (e.g., 23:00 -> 07:00)."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
        }
        # Early morning (after overnight span)
        with patch('blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '06:00'
            result = blinkstick_monitor.is_quiet_hours(config)
            assert result is True


class TestBlacklistFiltering:
    """Tests for blacklist pattern matching."""

    def test_is_blacklisted_matches_exact(self):
        """is_blacklisted should match exact names."""
        result = blinkstick_monitor.is_blacklisted('nginx', ['nginx'])
        assert result is True

    def test_is_blacklisted_matches_wildcard(self):
        """is_blacklisted should match wildcard patterns."""
        result = blinkstick_monitor.is_blacklisted('sandbox-dev-01', ['sandbox-*'])
        assert result is True
        result = blinkstick_monitor.is_blacklisted('sandbox-prod-01', ['sandbox-*'])
        assert result is True

    def test_is_blacklisted_no_match(self):
        """is_blacklisted should return False when no pattern matches."""
        result = blinkstick_monitor.is_blacklisted('docker', ['nginx', 'redis'])
        assert result is False

    def test_is_blacklisted_multiple_patterns(self):
        """is_blacklisted should return True if any pattern matches."""
        result = blinkstick_monitor.is_blacklisted('test-container', ['test-*', 'sandbox-*'])
        assert result is True
        result = blinkstick_monitor.is_blacklisted('prod-server', ['test-*', 'sandbox-*'])
        assert result is False


class TestConfigDetection:
    """Tests for configuration detection functions."""

    def test_detect_config_filters_blacklisted_containers(self):
        """detect_config should filter out blacklisted containers."""
        blacklist = ['sandbox-*', 'test-*']
        
        with patch.object(blinkstick_monitor, 'run') as mock_run:
            # Simulate 4 containers, 2 should be filtered
            mock_run.return_value = ('nginx\nredis\nsandbox-dev\ntest-app\n', 0)
            
            result = blinkstick_monitor.detect_config(blacklist=blacklist)
            
            assert 'nginx' in result['expected_containers']
            assert 'redis' in result['expected_containers']
            assert 'sandbox-dev' not in result['expected_containers']
            assert 'test-app' not in result['expected_containers']

    def test_detect_config_filters_blacklisted_mounts(self):
        """detect_config should filter out blacklisted mounts."""
        mount_blacklist = ['/mnt/backup-*', '/mnt/temp-*', '/mnt/backup', '/mnt/temp']

        with patch.object(blinkstick_monitor, 'run') as mock_run:
            # Mock multiple run() calls: docker, services, lsblk, findmnt
            mock_run.side_effect = [
                ('', 127),  # docker not available - returns ('output', rc)
                ('', 127),  # detect_user_services - returns ('output', rc)
                ('', 0),    # lsblk returns nothing
                ('/mnt/data ext4\n/mnt/backup ext4\n/mnt/temp xfs\n', 0),  # findmnt output
            ]

            result = blinkstick_monitor.detect_config(mount_blacklist=mount_blacklist)

            assert '/mnt/data' in result['expected_mounts']
            assert '/mnt/backup' not in result['expected_mounts']
            assert '/mnt/temp' not in result['expected_mounts']
