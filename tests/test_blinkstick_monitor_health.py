"""
Tests for blinkstick-monitor.py health check functions (mocked).

These tests cover:
- check_docker: Docker container health checks
- check_services: Systemd service health checks
- check_block_devices: Block device presence checks
- check_mounts: Mount point accessibility checks
- check_disk_usage: Disk usage threshold checks
- check_load: System load average checks
- run_all_checks: Combined health checks
- determine_color: Color determination based on issues
"""

import pytest
from unittest import mock
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


class TestRunFunction:
    """Tests for run function (subprocess wrapper)."""

    def test_run_success(self):
        """Test run function with successful command."""
        stdout, rc = blinkstick_monitor.run(['echo', 'hello'])
        assert rc == 0
        assert stdout == 'hello'

    def test_run_file_not_found(self):
        """Test run function with non-existent command."""
        stdout, rc = blinkstick_monitor.run(['nonexistentcommand12345'])
        assert rc == 127
        assert stdout == ''

    def test_run_timeout(self):
        """Test run function with timeout."""
        stdout, rc = blinkstick_monitor.run(['sleep', '5'], timeout=1)
        assert rc == 1
        assert 'timed out' in stdout

    def test_run_exception(self):
        """Test run function handles exceptions gracefully."""
        stdout, rc = blinkstick_monitor.run(['cat'])
        assert rc == 0


class TestDockerCheck:
    """Tests for check_docker function."""

    def test_docker_monitor_disabled(self):
        """Test check_docker returns empty when monitor_docker is False."""
        config = {'monitor_docker': False}
        issues = blinkstick_monitor.check_docker(config)
        assert issues == []

    def test_docker_command_fail(self):
        """Test check_docker returns critical issue when Docker unreachable."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app1', 'app2']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Cannot reach Docker daemon' in issues[0][1]

    def test_docker_container_missing(self):
        """Test check_docker detects missing containers."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app1', 'app2', 'app3']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('app1\tUp 5 hours\napp3\tUp 2 hours', 0)
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Container missing: app2' in issues[0][1]

    def test_docker_container_down(self):
        """Test check_docker detects containers that are not up."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app1']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('app1\tExited (1) 2 hours ago', 0)
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Container down: app1' in issues[0][1]

    def test_docker_container_unhealthy(self):
        """Test check_docker detects unhealthy containers as warning."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app1']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('app1\tUp (unhealthy) 5 hours', 0)
            issues = blinkstick_monitor.check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Container unhealthy: app1' in issues[0][1]

    def test_docker_container_healthy(self):
        """Test check_docker returns no issues for healthy container."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app1']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('app1\tUp 5 hours', 0)
            issues = blinkstick_monitor.check_docker(config)
            assert issues == []


class TestServicesCheck:
    """Tests for check_services function."""

    def test_services_monitor_disabled(self):
        """Test check_services returns empty when monitor_services is False."""
        config = {'monitor_services': False}
        issues = blinkstick_monitor.check_services(config)
        assert issues == []

    def test_service_down(self):
        """Test check_services detects service that is down."""
        config = {
            'monitor_services': True,
            'expected_services': ['app.service']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            # First call: is-active returns failure (rc=1)
            # Second call: systemctl cat succeeds (rc=0) meaning service exists but is down
            mock_run.side_effect = [
                ('', 1),  # is-active returns failure
                ('', 0)   # systemctl cat succeeds - service exists but is down
            ]
            issues = blinkstick_monitor.check_services(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Service down: app.service' in issues[0][1]

    def test_service_removed(self):
        """Test check_services detects removed service as warning."""
        config = {
            'monitor_services': True,
            'expected_services': ['removed.service']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            # First call: service not active
            # Second call: service file doesn't exist
            mock_run.side_effect = [
                ('', 1),  # is-active returns failure
                ('', 1)   # systemctl cat returns failure (removed)
            ]
            issues = blinkstick_monitor.check_services(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Service removed: removed.service' in issues[0][1]

    def test_service_active(self):
        """Test check_services returns no issues for active service."""
        config = {
            'monitor_services': True,
            'expected_services': ['app.service']
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 0)  # Service is active
            issues = blinkstick_monitor.check_services(config)
            assert issues == []


class TestBlockDevicesCheck:
    """Tests for check_block_devices function."""

    def test_lsblk_command_fail(self):
        """Test check_block_devices returns warning when lsblk fails."""
        config = {'expected_block_devices': ['sda', 'sdb']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)
            issues = blinkstick_monitor.check_block_devices(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Cannot run lsblk' in issues[0][1]

    def test_block_device_missing(self):
        """Test check_block_devices detects missing block device."""
        config = {'expected_block_devices': ['sda', 'sdb']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('sda\nnvme0n1', 0)
            issues = blinkstick_monitor.check_block_devices(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Block device missing: sdb' in issues[0][1]

    def test_all_block_devices_present(self):
        """Test check_block_devices returns no issues when all devices present."""
        config = {'expected_block_devices': ['sda', 'sdb', 'nvme0n1']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('sda\nsdb\nnvme0n1', 0)
            issues = blinkstick_monitor.check_block_devices(config)
            assert issues == []


class TestMountsCheck:
    """Tests for check_mounts function."""

    def test_findmnt_command_fail(self):
        """Test check_mounts returns warning when findmnt fails."""
        config = {'expected_mounts': ['/home', '/var']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('', 1)
            issues = blinkstick_monitor.check_mounts(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Cannot run findmnt' in issues[0][1]

    def test_mount_missing(self):
        """Test check_mounts detects missing mount point."""
        config = {'expected_mounts': ['/home', '/var', '/data']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('/home\n/var', 0)
            issues = blinkstick_monitor.check_mounts(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Mount missing: /data' in issues[0][1]

    def test_all_mounts_present(self):
        """Test check_mounts returns no issues when all mounts present."""
        config = {'expected_mounts': ['/home', '/var', '/data']}
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('/home\n/var\n/data', 0)
            issues = blinkstick_monitor.check_mounts(config)
            assert issues == []


class TestDiskUsageCheck:
    """Tests for check_disk_usage function."""

    def test_disk_usage_normal(self):
        """Test check_disk_usage returns no issues when disk usage normal."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': []
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('85 /home\n50 /var', 0)
            issues = blinkstick_monitor.check_disk_usage(config)
            assert issues == []

    def test_disk_usage_warning(self):
        """Test check_disk_usage detects high disk usage."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': []
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            # df output includes header line
            mock_run.return_value = ('Pcent Target\n90 /home\n88 /var', 0)
            issues = blinkstick_monitor.check_disk_usage(config)
            assert len(issues) == 2
            assert all(issue[0] == 'warning' for issue in issues)
            assert 'Disk /home at 90%' in issues[0][1]
            assert 'Disk /var at 88%' in issues[1][1]

    def test_disk_usage_below_threshold(self):
        """Test check_disk_usage does not warn when below threshold."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': []
        }
        with mock.patch.object(blinkstick_monitor, 'run') as mock_run:
            mock_run.return_value = ('84 /home\n50 /var', 0)
            issues = blinkstick_monitor.check_disk_usage(config)
            assert issues == []


class TestLoadCheck:
    """Tests for check_load function."""

    def test_load_normal(self):
        """Test check_load returns no issues when load normal."""
        config = {'load_warn_multiplier': 2.0}
        with mock.patch('os.cpu_count') as mock_cpu:
            mock_cpu.return_value = 4
            with mock.patch('os.getloadavg') as mock_load:
                mock_load.return_value = (1.5, 1.2, 1.0)
                issues = blinkstick_monitor.check_load(config)
                assert issues == []

    def test_load_high(self):
        """Test check_load detects high load."""
        config = {'load_warn_multiplier': 2.0}
        with mock.patch('os.cpu_count') as mock_cpu:
            mock_cpu.return_value = 4
            with mock.patch('os.getloadavg') as mock_load:
                mock_load.return_value = (10.5, 8.2, 7.0)
                issues = blinkstick_monitor.check_load(config)
                assert len(issues) == 1
                assert issues[0][0] == 'warning'
                assert 'High load' in issues[0][1]

    def test_no_loadavg_support(self):
        """Test check_load handles systems without getloadavg."""
        config = {'load_warn_multiplier': 2.0}
        with mock.patch('os.cpu_count') as mock_cpu:
            mock_cpu.return_value = 1
            with mock.patch('os.getloadavg') as mock_load:
                mock_load.side_effect = OSError("No load avg")
                issues = blinkstick_monitor.check_load(config)
                assert issues == []


class TestRunAllChecks:
    """Tests for run_all_checks function."""

    def test_no_issues_all_checks_pass(self):
        """Test run_all_checks returns empty when all healthy."""
        config = {}
        with mock.patch.object(blinkstick_monitor, 'check_docker') as mock_docker:
            with mock.patch.object(blinkstick_monitor, 'check_services') as mock_services:
                with mock.patch.object(blinkstick_monitor, 'check_block_devices') as mock_blocks:
                    with mock.patch.object(blinkstick_monitor, 'check_mounts') as mock_mounts:
                        with mock.patch.object(blinkstick_monitor, 'check_disk_usage') as mock_disk:
                            with mock.patch.object(blinkstick_monitor, 'check_load') as mock_load:
                                mock_docker.return_value = []
                                mock_services.return_value = []
                                mock_blocks.return_value = []
                                mock_mounts.return_value = []
                                mock_disk.return_value = []
                                mock_load.return_value = []
                                issues = blinkstick_monitor.run_all_checks(config)
                                assert issues == []

    def test_mixed_issues(self):
        """Test run_all_checks combines issues from all checks."""
        config = {}
        with mock.patch.object(blinkstick_monitor, 'check_docker') as mock_docker:
            with mock.patch.object(blinkstick_monitor, 'check_services') as mock_services:
                mock_docker.return_value = [
                    ('critical', 'Container down: app1'),
                    ('warning', 'Container unhealthy: app2')
                ]
                mock_services.return_value = [
                    ('critical', 'Service down: nginx')
                ]
                issues = blinkstick_monitor.run_all_checks(config)
                assert len(issues) == 3


class TestDetermineColor:
    """Tests for determine_color function."""

    def test_no_issues_green(self):
        """Test determine_color returns GREEN with no issues."""
        issues = []
        color, label = blinkstick_monitor.determine_color(issues)
        assert label == 'GREEN'
        assert color == blinkstick_monitor.COLOR_GREEN

    def test_warnings_yellow(self):
        """Test determine_color returns YELLOW with warnings only."""
        issues = [
            ('warning', 'Disk /home at 88%'),
            ('warning', 'High load: 8.5')
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert label == 'YELLOW'
        assert color == blinkstick_monitor.COLOR_YELLOW

    def test_critical_red(self):
        """Test determine_color returns RED with critical issues."""
        issues = [
            ('critical', 'Container down: app1'),
            ('warning', 'Disk /home at 88%')
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert label == 'RED'
        assert color == blinkstick_monitor.COLOR_RED

    def test_multiple_criticals_red(self):
        """Test multiple critical issues still returns RED."""
        issues = [
            ('critical', 'Container down: app1'),
            ('critical', 'Service down: nginx'),
            ('critical', 'Mount missing: /data')
        ]
        color, label = blinkstick_monitor.determine_color(issues)
        assert label == 'RED'
        assert color == blinkstick_monitor.COLOR_RED


class TestCmdStatus:
    """Tests for cmd_status function."""

    def test_status_all_ok(self):
        """Test cmd_status returns 0 when all healthy."""
        config = {
            'monitor_docker': False,
            'monitor_services': False
        }
        with mock.patch.object(blinkstick_monitor, 'run_all_checks') as mock_checks:
            mock_checks.return_value = []
            exit_code = blinkstick_monitor.cmd_status(config)
            assert exit_code == 0

    def test_status_with_critical(self):
        """Test cmd_status returns 2 with critical issues."""
        config = {}
        with mock.patch.object(blinkstick_monitor, 'run_all_checks') as mock_checks:
            mock_checks.return_value = [
                ('critical', 'Container down: app1')
            ]
            exit_code = blinkstick_monitor.cmd_status(config)
            assert exit_code == 2

    def test_status_with_warning_only(self):
        """Test cmd_status returns 1 with warning only."""
        config = {}
        with mock.patch.object(blinkstick_monitor, 'run_all_checks') as mock_checks:
            mock_checks.return_value = [
                ('warning', 'Disk /home at 88%')
            ]
            exit_code = blinkstick_monitor.cmd_status(config)
            assert exit_code == 1
