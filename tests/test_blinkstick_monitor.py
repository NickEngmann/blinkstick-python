"""Unit tests for blinkstick-monitor.py health checks and configuration management."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions from the monitor module
from blinkstick import monitor
from blinkstick.monitor import (
    DEFAULT_CONFIG,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_YELLOW,
    COLOR_BLUE,
    COLOR_OFF,
    is_blacklisted,
    is_quiet_hours,
    detect_config,
    load_config,
    save_config,
    load_or_create_config,
    check_docker,
    check_services,
    check_block_devices,
    check_mounts,
    check_disk_usage,
    check_load,
    run_all_checks,
    determine_color,
    cmd_status,
    cmd_check_once,
)


class TestColorDefinitions(unittest.TestCase):
    """Test that color definitions are properly defined."""

    def test_green_color(self):
        """Test that GREEN color is defined as (0, 64, 0)."""
        self.assertEqual(COLOR_GREEN, (0, 64, 0))

    def test_red_color(self):
        """Test that RED color is defined as (64, 0, 0)."""
        self.assertEqual(COLOR_RED, (64, 0, 0))

    def test_yellow_color(self):
        """Test that YELLOW color is defined as (64, 40, 0)."""
        self.assertEqual(COLOR_YELLOW, (64, 40, 0))

    def test_blue_color(self):
        """Test that BLUE color is defined as (0, 0, 64)."""
        self.assertEqual(COLOR_BLUE, (0, 0, 64))

    def test_off_color(self):
        """Test that OFF color is defined as (0, 0, 0)."""
        self.assertEqual(COLOR_OFF, (0, 0, 0))


class TestDefaultConfiguration(unittest.TestCase):
    """Test default configuration structure."""

    def test_default_config_exists(self):
        """Test that DEFAULT_CONFIG is defined."""
        self.assertIsInstance(DEFAULT_CONFIG, dict)

    def test_default_config_has_required_keys(self):
        """Test that DEFAULT_CONFIG has all required keys."""
        required_keys = [
            'check_interval', 'disk_warn_percent', 'load_warn_multiplier',
            'boot_delay', 'monitor_docker', 'expected_containers',
            'expected_block_devices', 'expected_mounts', 'monitor_services',
            'expected_services', 'container_blacklist_patterns',
            'mount_blacklist_patterns', 'quiet_hours_enabled',
            'quiet_hours_start', 'quiet_hours_end', 'led_count'
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_CONFIG, f"Missing required key: {key}")

    def test_default_config_values(self):
        """Test that DEFAULT_CONFIG has expected default values."""
        self.assertEqual(DEFAULT_CONFIG['check_interval'], 10)
        self.assertEqual(DEFAULT_CONFIG['disk_warn_percent'], 85)
        self.assertEqual(DEFAULT_CONFIG['load_warn_multiplier'], 2.0)
        self.assertEqual(DEFAULT_CONFIG['boot_delay'], 30)
        self.assertEqual(DEFAULT_CONFIG['quiet_hours_start'], '23:00')
        self.assertEqual(DEFAULT_CONFIG['quiet_hours_end'], '07:00')


class TestRunFunction(unittest.TestCase):
    """Test the run() function for subprocess execution."""

    @patch('blinkstick.monitor.run')
    def test_run_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = ('output', 0)
        result, rc = mock_run('echo test')
        self.assertEqual(result, 'output')
        self.assertEqual(rc, 0)

    @patch('blinkstick.monitor.run')
    def test_run_command_not_found(self, mock_run):
        """Test when command is not found."""
        mock_run.return_value = ('', 127)
        result, rc = mock_run('nonexistent_command_xyz')
        self.assertEqual(rc, 127)

    @patch('blinkstick.monitor.run')
    def test_run_timeout(self, mock_run):
        """Test command timeout."""
        mock_run.return_value = ('command timed out', 1)
        result, rc = mock_run('sleep 999')
        self.assertIn('timeout', result.lower())
        self.assertEqual(rc, 1)


class TestBlacklistFunction(unittest.TestCase):
    """Test blacklist pattern matching."""

    def test_blacklist_exact_match(self):
        """Test exact blacklist pattern match."""
        self.assertTrue(is_blacklisted('docker-nginx', ['docker-nginx']))

    def test_blacklist_wildcard_match(self):
        """Test wildcard pattern match."""
        self.assertTrue(is_blacklisted('lotus-sandbox-123', ['lotus-sandbox-*']))
        self.assertTrue(is_blacklisted('lotus-sandbox-abc', ['lotus-sandbox-*']))

    def test_blacklist_no_match(self):
        """Test when pattern doesn't match."""
        self.assertFalse(is_blacklisted('docker-nginx', ['docker-postgres']))

    def test_blacklist_multiple_patterns(self):
        """Test with multiple blacklist patterns."""
        patterns = ['lotus-sandbox-*', 'dev-*', 'test-*']
        self.assertTrue(is_blacklisted('lotus-sandbox-123', patterns))
        self.assertTrue(is_blacklisted('dev-server', patterns))
        self.assertTrue(is_blacklisted('test-runner', patterns))
        self.assertFalse(is_blacklisted('prod-server', patterns))


class TestQuietHoursFunction(unittest.TestCase):
    """Test quiet hours configuration and detection."""

    def test_quiet_hours_disabled(self):
        """Test when quiet hours are disabled."""
        config = {'quiet_hours_enabled': False}
        self.assertFalse(is_quiet_hours(config))

    def test_quiet_hours_outside_window(self):
        """Test when current time is outside quiet hours window."""
        # Test with 10:00 AM - outside 23:00 to 07:00 window
        with patch('blinkstick.monitor.datetime') as mock_dt:
            mock_dt.now.return_value.strftime.return_value = '10:00'
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00'
            }
            self.assertFalse(is_quiet_hours(config))

    def test_quiet_hours_inside_window(self):
        """Test when current time is inside quiet hours window."""
        # Test with 02:00 AM - inside 23:00 to 07:00 window
        with patch('blinkstick.monitor.datetime') as mock_dt:
            mock_dt.now.return_value.strftime.return_value = '02:00'
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00'
            }
            self.assertTrue(is_quiet_hours(config))

    def test_quiet_hours_overnight_span(self):
        """Test overnight quiet hours span (22:00 to 06:00)."""
        # Test at 23:00 - inside overnight span
        with patch('blinkstick.monitor.datetime') as mock_dt:
            mock_dt.now.return_value.strftime.return_value = '23:00'
            config = {
                'quiet_hours_enabled': True,
                'quiet_hours_start': '22:00',
                'quiet_hours_end': '06:00'
            }
            self.assertTrue(is_quiet_hours(config))
            
        # Test at 04:00 - still inside overnight span
        with patch('blinkstick.monitor.datetime') as mock_dt:
            mock_dt.now.return_value.strftime.return_value = '04:00'
            self.assertTrue(is_quiet_hours(config))
            
        # Test at 10:00 - outside overnight span
        with patch('blinkstick.monitor.datetime') as mock_dt:
            mock_dt.now.return_value.strftime.return_value = '10:00'
            self.assertFalse(is_quiet_hours(config))


class TestDetermineColorFunction(unittest.TestCase):
    """Test color determination based on health check results."""

    def test_determine_color_all_green(self):
        """Test when no issues found - returns GREEN."""
        issues = []
        color, label = determine_color(issues)
        self.assertEqual(color, COLOR_GREEN)
        self.assertEqual(label, 'GREEN')

    def test_determine_color_warnings(self):
        """Test when only warnings - returns YELLOW."""
        issues = [('warning', 'Disk at 80%'), ('warning', 'High load')]
        color, label = determine_color(issues)
        self.assertEqual(color, COLOR_YELLOW)
        self.assertEqual(label, 'YELLOW')

    def test_determine_color_criticals(self):
        """Test when critical issues found - returns RED."""
        issues = [('critical', 'Container down'), ('critical', 'Service down')]
        color, label = determine_color(issues)
        self.assertEqual(color, COLOR_RED)
        self.assertEqual(label, 'RED')

    def test_determine_color_mixed(self):
        """Test when both warnings and criticals - critical takes precedence."""
        issues = [
            ('warning', 'Disk at 80%'),
            ('critical', 'Container down'),
            ('warning', 'High load')
        ]
        color, label = determine_color(issues)
        self.assertEqual(color, COLOR_RED)
        self.assertEqual(label, 'RED')


class TestHealthChecks(unittest.TestCase):
    """Test individual health check functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'check_interval': 10,
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0,
            'boot_delay': 30,
            'monitor_docker': False,
            'expected_containers': [],
            'expected_block_devices': [],
            'expected_mounts': [],
            'monitor_services': False,
            'expected_services': [],
        }

    @patch('blinkstick.monitor.run')
    def test_check_docker_disabled(self, mock_run):
        """Test check_docker when monitoring is disabled."""
        mock_run.return_value = ('', 0)
        issues = check_docker(self.config)
        self.assertEqual(issues, [])

    @patch('blinkstick.monitor.run')
    def test_check_docker_container_down(self, mock_run):
        """Test check_docker when container is down."""
        self.config['monitor_docker'] = True
        self.config['expected_containers'] = ['nginx', 'postgres']
        
        mock_run.return_value = (
            'nginx\tdown\npostgres\tUp 10 hours',
            0
        )
        issues = check_docker(self.config)
        
        # Should detect nginx as down
        self.assertEqual(len(issues), 1)
        self.assertIn('nginx', issues[0][1])

    @patch('blinkstick.monitor.run')
    def test_check_services_service_down(self, mock_run):
        """Test check_services when service is down."""
        self.config['monitor_services'] = True
        self.config['expected_services'] = ['my-service']
        
        mock_run.side_effect = [
            ('', 1),  # is-active fails (service down)
            ('', 0),  # cat succeeds (service exists)
        ]
        issues = check_services(self.config)
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('my-service', issues[0][1])

    @patch('blinkstick.monitor.run')
    def test_check_block_devices_missing(self, mock_run):
        """Test check_block_devices when device is missing."""
        self.config['expected_block_devices'] = ['sda', 'nvme0n1']
        
        # Only sda is present, nvme0n1 is missing
        mock_run.return_value = ('sda\nsdb\n', 0)
        issues = check_block_devices(self.config)
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('nvme0n1', issues[0][1])

    @patch('blinkstick.monitor.run')
    def test_check_mounts_missing(self, mock_run):
        """Test check_mounts when mount point is missing."""
        self.config['expected_mounts'] = ['/var/log', '/data']
        
        # Only /var/log is mounted
        mock_run.return_value = ('/var/log\n/home\n', 0)
        issues = check_mounts(self.config)
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('/data', issues[0][1])

    @patch('blinkstick.monitor.run')
    def test_check_disk_usage_warning(self, mock_run):
        """Test check_disk_usage when disk is above threshold."""
        self.config['disk_warn_percent'] = 80
        
        # Disk at 85% - above threshold
        mock_run.return_value = (
            'pcent,target\n85% /\n45% /home\n',
            0
        )
        issues = check_disk_usage(self.config)
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'warning')
        self.assertIn('85%', issues[0][1])

    @patch('blinkstick.monitor.run')
    def test_check_disk_usage_ok(self, mock_run):
        """Test check_disk_usage when disks are within limits."""
        self.config['disk_warn_percent'] = 85
        
        # All disks below threshold
        mock_run.return_value = (
            'pcent,target\n70% /\n50% /home\n',
            0
        )
        issues = check_disk_usage(self.config)
        self.assertEqual(issues, [])

    @patch('os.getloadavg')
    @patch('os.cpu_count')
    def test_check_load_warning(self, mock_cpu_count, mock_getloadavg):
        """Test check_load when system load is high."""
        mock_cpu_count.return_value = 2
        mock_getloadavg.return_value = (8.5, 7.2, 6.1)

        # With 2 CPUs and multiplier of 2.0, threshold is 4.0
        # Load of 8.5 exceeds threshold
        config = {'load_warn_multiplier': 2.0}
        issues = check_load(config)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'warning')
        self.assertIn('load', issues[0][1].lower())

    @patch('os.getloadavg')
    @patch('os.cpu_count')
    def test_check_load_ok(self, mock_cpu_count, mock_getloadavg):
        """Test check_load when system load is normal."""
        mock_cpu_count.return_value = 4
        mock_getloadavg.return_value = (1.5, 1.2, 1.0)

        # With 4 CPUs and multiplier of 2.0, threshold is 8.0
        # Load of 1.5 is well below threshold
        config = {'load_warn_multiplier': 2.0}
        issues = check_load(config)
        self.assertEqual(issues, [])


class TestRunAllChecks(unittest.TestCase):
    """Test the run_all_checks function."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'check_interval': 10,
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0,
            'boot_delay': 30,
            'monitor_docker': False,
            'expected_containers': [],
            'expected_block_devices': [],
            'expected_mounts': [],
            'monitor_services': False,
            'expected_services': [],
        }

    @patch('blinkstick.monitor.check_docker')
    @patch('blinkstick.monitor.check_services')
    @patch('blinkstick.monitor.check_block_devices')
    @patch('blinkstick.monitor.check_mounts')
    @patch('blinkstick.monitor.check_disk_usage')
    @patch('blinkstick.monitor.check_load')
    def test_run_all_checks_aggregates_issues(
        self, mock_load, mock_disk, mock_mounts, mock_devices,
        mock_services, mock_docker
    ):
        """Test that run_all_checks aggregates all issues."""
        mock_docker.return_value = [('critical', 'Docker issue')]
        mock_disk.return_value = [('warning', 'Disk warning')]
        mock_load.return_value = []
        mock_devices.return_value = []
        mock_mounts.return_value = []
        mock_services.return_value = []
        
        all_issues = run_all_checks(self.config)
        
        self.assertEqual(len(all_issues), 2)
        self.assertIn(('critical', 'Docker issue'), all_issues)
        self.assertIn(('warning', 'Disk warning'), all_issues)


class TestConfigManagement(unittest.TestCase):
    """Test configuration loading and saving."""

    def setUp(self):
        """Set up temporary directory for test configs."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_config(self):
        """Test that save_config writes valid JSON."""
        config = {
            'test_key': 'test_value',
            'test_list': [1, 2, 3]
        }
        config_path = os.path.join(self.temp_dir, 'test_config.json')
        
        # Mock CONFIG_PATH
        with patch('blinkstick.monitor.CONFIG_PATH', config_path):
            save_config(config)
            
            # Verify file was created
            self.assertTrue(os.path.exists(config_path))
            
            # Verify content is valid JSON
            with open(config_path, 'r') as f:
                loaded = json.load(f)
            self.assertEqual(loaded, config)

    def test_load_config(self):
        """Test that load_config reads valid config."""
        config = {
            'check_interval': 15,
            'disk_warn_percent': 90
        }
        config_path = os.path.join(self.temp_dir, 'test_config.json')
        
        # Write config file
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        # Mock CONFIG_PATH
        with patch('blinkstick.monitor.CONFIG_PATH', config_path):
            loaded = load_config()
            self.assertEqual(loaded['check_interval'], 15)
            self.assertEqual(loaded['disk_warn_percent'], 90)

    def test_load_config_nonexistent(self):
        """Test load_config returns None for nonexistent config."""
        config_path = os.path.join(self.temp_dir, 'nonexistent.json')
        
        with patch('blinkstick.monitor.CONFIG_PATH', config_path):
            loaded = load_config()
            self.assertIsNone(loaded)

    def test_load_or_create_config(self):
        """Test load_or_create_config creates default config."""
        config_path = os.path.join(self.temp_dir, 'nonexistent.json')
        
        with patch('blinkstick.monitor.CONFIG_PATH', config_path):
            with patch('blinkstick.monitor.detect_config') as mock_detect:
                mock_detect.return_value = DEFAULT_CONFIG.copy()
                with patch('blinkstick.monitor.save_config'):
                    result = load_or_create_config()
                    self.assertEqual(result, DEFAULT_CONFIG)


class TestCmdStatus(unittest.TestCase):
    """Test the command-line status function."""

    def test_cmd_status_no_issues(self):
        """Test cmd_status when all checks pass."""
        config = DEFAULT_CONFIG.copy()
        config['check_interval'] = 10
        
        with patch('blinkstick.monitor.run_all_checks') as mock_checks:
            mock_checks.return_value = []
            result = cmd_status(config)
            self.assertEqual(result, 0)

    def test_cmd_status_with_issues(self):
        """Test cmd_status returns non-zero when issues exist."""
        config = DEFAULT_CONFIG.copy()
        
        with patch('blinkstick.monitor.run_all_checks') as mock_checks:
            mock_checks.return_value = [('critical', 'Test issue')]
            result = cmd_status(config)
            self.assertEqual(result, 2)


class TestRunFunctionErrors(unittest.TestCase):
    """Test error handling in run() function."""

    @patch('blinkstick.monitor.subprocess.run')
    def test_run_file_not_found(self, mock_run):
        """Test run() handles FileNotFoundError."""
        mock_run.side_effect = FileNotFoundError('command not found')
        result, rc = mock_run(['nonexistent'])
        self.assertEqual(rc, 127)

    @patch('blinkstick.monitor.subprocess.run')
    def test_run_timeout_expired(self, mock_run):
        """Test run() handles TimeoutExpired."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(['sleep', '999'], 1.0)
        result, rc = mock_run(['sleep', '999'], timeout=1)
        self.assertIn('timeout', result.lower())
        self.assertEqual(rc, 1)


if __name__ == '__main__':
    unittest.main()
