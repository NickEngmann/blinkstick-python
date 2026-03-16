"""
Tests for health check logic (mocked).
"""
import pytest
import tests.conftest as fixtures
from unittest.mock import patch, MagicMock

# Import functions we need to test
check_docker = fixtures.pytest_blinkstick_monitor.check_docker
check_services = fixtures.pytest_blinkstick_monitor.check_services
check_block_devices = fixtures.pytest_blinkstick_monitor.check_block_devices
check_mounts = fixtures.pytest_blinkstick_monitor.check_mounts
check_disk_usage = fixtures.pytest_blinkstick_monitor.check_disk_usage
check_load = fixtures.pytest_blinkstick_monitor.check_load
run_all_checks = fixtures.pytest_blinkstick_monitor.run_all_checks
is_quiet_hours = fixtures.pytest_blinkstick_monitor.is_quiet_hours
detect_user_services = fixtures.pytest_blinkstick_monitor.detect_user_services


class TestHealthChecks:
    """Test all health check functions."""

    def test_check_docker_disabled_returns_empty(self):
        """When docker monitoring is disabled, should return no issues."""
        config = {'monitor_docker': False, 'expected_containers': []}
        issues = check_docker(config)
        assert issues == []

    def test_check_docker_docker_unreachable(self):
        """When docker daemon is unreachable, should report critical issue."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx']
        }

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = ('', 1)  # Docker command failed

            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Cannot reach Docker daemon' in issues[0][1]

    def test_check_docker_container_missing(self):
        """When expected container is missing, should report critical issue."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx', 'redis']
        }

        # Only nginx is running
        docker_output = 'nginx\tUp 5 hours\npostgres\tUp 1 day'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (docker_output, 0)

            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Container missing: redis' in issues[0][1]

    def test_check_docker_container_down(self):
        """When container status doesn't contain 'Up', should report critical."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['app']
        }

        # Container status doesn't have 'Up'
        docker_output = 'app\tExited (1) 2 hours ago'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (docker_output, 0)

            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Container down' in issues[0][1]

    def test_check_docker_container_unhealthy(self):
        """When container status contains 'unhealthy', should report warning."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['web']
        }

        docker_output = 'web\tUp 2 hours (unhealthy)'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (docker_output, 0)

            issues = check_docker(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Container unhealthy' in issues[0][1]

    def test_check_docker_all_containers_healthy(self):
        """When all containers are healthy, should return no issues."""
        config = {
            'monitor_docker': True,
            'expected_containers': ['nginx', 'redis', 'postgres']
        }

        docker_output = (
            'nginx\tUp 5 hours\n'
            'redis\tUp 3 hours\n'
            'postgres\tUp 1 day'
        )

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (docker_output, 0)

            issues = check_docker(config)
            assert issues == []

    def test_check_services_disabled_returns_empty(self):
        """When services monitoring is disabled, should return no issues."""
        config = {'monitor_services': False, 'expected_services': []}
        issues = check_services(config)
        assert issues == []

    def test_check_services_service_down(self):
        """When expected service is down (but exists), should report critical."""
        config = {
            'monitor_services': True,
            'expected_services': ['myapp.service']
        }

        def run_side_effect(cmd, *args, **kwargs):
            if 'is-active' in cmd:
                return ('', 1)  # Service is not active
            elif 'cat' in cmd:
                return ('', 0)  # Service exists (but is down)
            return ('', 0)

        with patch('tests.conftest.pytest_blinkstick_monitor.run', side_effect=run_side_effect):
            issues = check_services(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Service down: myapp.service' in issues[0][1]

    def test_check_services_service_removed(self):
        """When service no longer exists, should report warning."""
        config = {
            'monitor_services': True,
            'expected_services': ['oldservice.service']
        }

        def run_side_effect(cmd, *args, **kwargs):
            if 'is-active' in cmd:
                return ('', 1)  # Not active
            elif 'cat' in cmd:
                return ('', 1)  # Service file doesn't exist
            return ('', 0)

        with patch('tests.conftest.pytest_blinkstick_monitor.run', side_effect=run_side_effect):
            issues = check_services(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Service removed: oldservice.service' in issues[0][1]

    def test_check_services_all_healthy(self):
        """When all services are running, should return no issues."""
        config = {
            'monitor_services': True,
            'expected_services': ['service1', 'service2']
        }

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = ('active', 0)  # Service is active

            issues = check_services(config)
            assert issues == []

    def test_check_block_devices_missing(self):
        """When expected block device is missing, should report critical."""
        config = {
            'expected_block_devices': ['sda', 'sdb']
        }

        # Only sda is present
        lsblk_output = 'sda\nsdc\n'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (lsblk_output, 0)

            issues = check_block_devices(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Block device missing: sdb' in issues[0][1]

    def test_check_block_devices_all_present(self):
        """When all block devices are present, should return no issues."""
        config = {
            'expected_block_devices': ['sda', 'sdb', 'nvme0n1']
        }

        lsblk_output = 'sda\nsdb\nnvme0n1\n'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (lsblk_output, 0)

            issues = check_block_devices(config)
            assert issues == []

    def test_check_mounts_missing(self):
        """When expected mount is missing, should report critical."""
        config = {
            'expected_mounts': ['/home', '/data']
        }

        # Only /home is mounted
        findmnt_output = '/home\n/efi\n'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (findmnt_output, 0)

            issues = check_mounts(config)
            assert len(issues) == 1
            assert issues[0][0] == 'critical'
            assert 'Mount missing: /data' in issues[0][1]

    def test_check_mounts_all_present(self):
        """When all mounts are present, should return no issues."""
        config = {
            'expected_mounts': ['/home', '/data', '/var']
        }

        findmnt_output = '/home\n/data\n/var\n'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (findmnt_output, 0)

            issues = check_mounts(config)
            assert issues == []

    def test_check_disk_usage_warning(self):
        """When disk usage exceeds threshold, should report warning."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': []
        }

        df_output = (
            'Pct Target\n'
            '87% /dev/sda1\n'
            '45% /dev/sdb1\n'
        )

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (df_output, 0)

            issues = check_disk_usage(config)
            assert len(issues) == 1
            assert issues[0][0] == 'warning'
            assert 'Disk /dev/sda1 at 87%' in issues[0][1]

    def test_check_disk_usage_blacklisted_mounts_ignored(self):
        """When disk usage warning matches blacklist pattern, should be ignored."""
        config = {
            'disk_warn_percent': 85,
            'mount_blacklist_patterns': ['/tmp-*']
        }

        df_output = (
            'Pct Target\n'
            '90% /tmp-blacklist\n'
            '87% /dev/sda1\n'
        )

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (df_output, 0)

            issues = check_disk_usage(config)
            # Only sda1 should trigger warning, not blacklisted tmp
            assert len(issues) == 1

    def test_check_disk_usage_no_warnings(self):
        """When all disk usage is below threshold, should return no issues."""
        config = {
            'disk_warn_percent': 90,
            'mount_blacklist_patterns': []
        }

        df_output = (
            'Pct Target\n'
            '45% /dev/sda1\n'
            '60% /dev/sdb1\n'
        )

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.return_value = (df_output, 0)

            issues = check_disk_usage(config)
            assert issues == []

    def test_check_load_warning(self):
        """When load exceeds threshold, should report warning."""
        config = {
            'load_warn_multiplier': 2.0
        }

        with patch('os.cpu_count', return_value=2):
            with patch('os.getloadavg', return_value=(5.0, 3.0, 2.0)):
                issues = check_load(config)
                assert len(issues) == 1
                assert issues[0][0] == 'warning'
                assert 'High load' in issues[0][1]

    def test_check_load_normal(self):
        """When load is within acceptable range, should return no issues."""
        config = {
            'load_warn_multiplier': 2.0
        }

        with patch('os.cpu_count', return_value=4):
            with patch('os.getloadavg', return_value=(2.0, 1.5, 1.0)):
                issues = check_load(config)
                assert issues == []

    def test_check_load_no_getloadavg(self):
        """When getloadavg fails (non-Linux), should return no issues."""
        config = {}

        with patch('os.cpu_count', return_value=1):
            with patch('os.getloadavg', side_effect=OSError('Not supported')):
                issues = check_load(config)
                assert issues == []

    def test_run_all_checks_returns_combined_issues(self):
        """run_all_checks should combine issues from all checks."""
        config = {
            'monitor_docker': True,
            'monitor_services': True,
            'expected_containers': ['missing'],
            'expected_services': ['down'],
            'expected_block_devices': [],
            'expected_mounts': [],
            'expected_block_devices': ['present'],
            'disk_warn_percent': 85,
            'load_warn_multiplier': 2.0
        }

        with patch('tests.conftest.pytest_blinkstick_monitor.check_docker', return_value=[('critical', 'docker issue')]):
            with patch('tests.conftest.pytest_blinkstick_monitor.check_services', return_value=[('critical', 'service issue')]):
                with patch('tests.conftest.pytest_blinkstick_monitor.check_block_devices', return_value=[]):
                    with patch('tests.conftest.pytest_blinkstick_monitor.check_mounts', return_value=[]):
                        with patch('tests.conftest.pytest_blinkstick_monitor.check_disk_usage', return_value=[]):
                            with patch('tests.conftest.pytest_blinkstick_monitor.check_load', return_value=[]):
                                issues = run_all_checks(config)
                                assert len(issues) == 2
                                assert any('docker issue' in i[1] for i in issues)
                                assert any('service issue' in i[1] for i in issues)


class TestQuietHours:
    """Test quiet hours logic."""

    def test_is_quiet_hours_disabled(self):
        """When quiet hours is disabled, should return False."""
        config = {
            'quiet_hours_enabled': False,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }

        # Mock datetime.now() to return a mock datetime with specific strftime result
        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '20:00'
            result = is_quiet_hours(config)
            assert result is False

    def test_is_quiet_hours_during_hours(self):
        """During quiet hours, should return True."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }

        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '01:00'
            result = is_quiet_hours(config)
            assert result is True

    def test_is_quiet_hours_outside_hours(self):
        """Outside quiet hours, should return False."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00'
        }

        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '12:00'
            result = is_quiet_hours(config)
            assert result is False

    def test_is_quiet_hours_overnight_span(self):
        """For overnight spans like 23:00-07:00, check correctly."""
        config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '06:00'
        }

        # At 23:00 (after start)
        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '23:00'
            assert is_quiet_hours(config) is True

        # At 05:00 (before end)
        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '05:00'
            assert is_quiet_hours(config) is True

        # At 08:00 (after end)
        with patch('tests.conftest.pytest_blinkstick_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '08:00'
            assert is_quiet_hours(config) is False


class TestDetectUserServices:
    """Test user service detection logic."""

    def test_detect_user_services_finds_active_services(self):
        """Should find active user-created services."""
        services_output = '/etc/systemd/system/myapp.service\n/etc/systemd/system/backend.service'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.side_effect = [
                (services_output, 0),  # find
                ('active', 0),         # systemctl is-active for myapp
                ('active', 0)          # systemctl is-active for backend
            ]

            services = detect_user_services()
            assert 'myapp.service' in services
            assert 'backend.service' in services
            assert len(services) == 2

    def test_detect_user_services_excludes_systemd_default(self):
        """Should exclude systemd default services that aren't user-created."""
        services_output = '/etc/systemd/system/dbus-org.test.service'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.side_effect = [
                (services_output, 0),  # find
                ('', 1)                # not a regular file (symlink)
            ]

            services = detect_user_services()
            # Should not include dbus-org.* services
            assert len(services) == 0

    def test_detect_user_services_excludes_blacklisted(self):
        """Should exclude blinkstick-monitor itself."""
        services_output = '/etc/systemd/system/blinkstick-monitor.service'

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.side_effect = [
                (services_output, 0),
                ('active', 0)
            ]

            services = detect_user_services()
            assert len(services) == 0
