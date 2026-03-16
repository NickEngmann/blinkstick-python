"""
Tests for configuration parsing, loading, saving, and detection logic.
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import tests.conftest as fixtures

# Import functions we need to test
load_config = fixtures.pytest_blinkstick_monitor.load_config
save_config = fixtures.pytest_blinkstick_monitor.save_config
detect_config = fixtures.pytest_blinkstick_monitor.detect_config
load_or_create_config = fixtures.pytest_blinkstick_monitor.load_or_create_config
DEFAULT_CONFIG = fixtures.pytest_blinkstick_monitor.DEFAULT_CONFIG
CONFIG_PATH = fixtures.pytest_blinkstick_monitor.CONFIG_PATH
is_blacklisted = fixtures.pytest_blinkstick_monitor.is_blacklisted


def mock_open(read_data=''):
    """Helper to create a mock file object for testing."""
    from unittest.mock import mock_open as unittest_mock_open
    return unittest_mock_open(read_data=read_data)


class TestConfigurationParsing:
    """Test configuration loading, saving, and parsing."""

    def test_load_config_returns_none_when_file_missing(self):
        """When config file doesn't exist, should return None."""
        with patch('tests.conftest.pytest_blinkstick_monitor.os.path.exists') as mock_exists:
            mock_exists.return_value = False
            result = load_config()
            assert result is None

    def test_load_config_returns_config_when_file_exists(self):
        """When config file exists with valid JSON, should return parsed config."""
        config_data = {
            'check_interval': 15,
            'disk_warn_percent': 90,
            'monitor_docker': True
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch('tests.conftest.pytest_blinkstick_monitor.CONFIG_PATH', temp_path):
                with patch('tests.conftest.pytest_blinkstick_monitor.os.path.exists', return_value=True):
                    with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
                        result = load_config()
                        assert result is not None
                        assert result['check_interval'] == 15
                        assert result['disk_warn_percent'] == 90
                        assert result['monitor_docker'] is True
        finally:
            os.unlink(temp_path)

    def test_load_config_handles_invalid_json(self):
        """When config file has invalid JSON, should return None and log error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write("this is not valid json {{{")
            temp_path = f.name

        try:
            with patch('tests.conftest.pytest_blinkstick_monitor.CONFIG_PATH', temp_path):
                with patch('tests.conftest.pytest_blinkstick_monitor.os.path.exists', return_value=True):
                    with patch('builtins.open', mock_open(read_data="invalid json")):
                        result = load_config()
                        assert result is None
        finally:
            os.unlink(temp_path)

    def test_load_config_merges_with_defaults(self):
        """Loading config should merge with DEFAULT_CONFIG values."""
        partial_config = {'check_interval': 30}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            json.dump(partial_config, f)
            temp_path = f.name

        try:
            with patch('tests.conftest.pytest_blinkstick_monitor.CONFIG_PATH', temp_path):
                with patch('tests.conftest.pytest_blinkstick_monitor.os.path.exists', return_value=True):
                    result = load_config()
                    # Should have our value
                    assert result['check_interval'] == 30
                    # Should have default value for missing keys
                    assert result['disk_warn_percent'] == DEFAULT_CONFIG['disk_warn_percent']
        finally:
            os.unlink(temp_path)

    def test_default_config_has_expected_keys(self):
        """DEFAULT_CONFIG should have all expected keys."""
        expected_keys = [
            'check_interval', 'disk_warn_percent', 'load_warn_multiplier',
            'boot_delay', 'monitor_docker', 'expected_containers',
            'expected_block_devices', 'expected_mounts', 'monitor_services',
            'expected_services', 'container_blacklist_patterns',
            'mount_blacklist_patterns', 'quiet_hours_enabled',
            'quiet_hours_start', 'quiet_hours_end', 'led_count'
        ]

        for key in expected_keys:
            assert key in DEFAULT_CONFIG, f"Missing key: {key}"


class TestDetectConfig:
    """Test configuration detection logic."""

    def test_detect_config_returns_default_values_when_no_system_info(self):
        """When no system info is available, should return defaults."""
        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            # Simulate docker not available
            mock_run.return_value = ('', 127)
            # Simulate no systemd services
            mock_run.return_value = ('', 0)

            result = detect_config()

            assert result['monitor_docker'] is False
            assert result['monitor_services'] is False
            assert result['expected_containers'] == []
            assert result['led_count'] == 2  # Default fallback

    def test_detect_config_with_docker_containers(self):
        """When docker is available, should detect running containers."""
        running_containers = ['nginx', 'redis', 'postgres']

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.side_effect = [
                (f'\n'.join(running_containers), 0),  # docker ps
                ('', 0),  # systemd services
                ('', 0),  # lsblk
                ('', 0),  # findmnt
                (None, None)  # detect_led_count
            ]

            with patch('tests.conftest.pytest_blinkstick_monitor.detect_led_count', return_value=2):
                result = detect_config()

                assert result['monitor_docker'] is True
                assert result['expected_containers'] == sorted(running_containers)

    def test_detect_config_preserves_blacklist(self):
        """detect_config should filter containers based on blacklist patterns."""
        all_containers = ['nginx', 'redis', 'lotus-sandbox-1', 'lotus-sandbox-2']
        blacklist = ['lotus-sandbox-*']

        with patch('tests.conftest.pytest_blinkstick_monitor.run') as mock_run:
            mock_run.side_effect = [
                (f'\n'.join(all_containers), 0),
                ('', 0),
                ('', 0),
                ('', 0),
                (None, None)
            ]

            with patch('tests.conftest.pytest_blinkstick_monitor.detect_led_count', return_value=2):
                result = detect_config(blacklist=blacklist)

                # Should only include non-blacklisted containers
                assert 'lotus-sandbox-1' not in result['expected_containers']
                assert 'lotus-sandbox-2' not in result['expected_containers']
                assert 'nginx' in result['expected_containers']
                assert result['container_blacklist_patterns'] == blacklist


class TestLoadOrCreateConfig:
    """Test load_or_create_config function."""

    def test_load_or_create_config_returns_existing_config(self):
        """Should return existing config if file is found."""
        existing_config = {'check_interval': 20}

        with patch('tests.conftest.pytest_blinkstick_monitor.load_config', return_value=existing_config):
            with patch('tests.conftest.pytest_blinkstick_monitor.log') as mock_log:
                result = load_or_create_config()

                assert result == existing_config
                mock_log.info.assert_called_with('Loaded config from /etc/blinkstick-monitor.conf')

    def test_load_or_create_config_creates_new_when_missing(self):
        """Should create new config when file doesn't exist."""
        with patch('tests.conftest.pytest_blinkstick_monitor.load_config', return_value=None):
            with patch('tests.conftest.pytest_blinkstick_monitor.detect_config', return_value={'check_interval': 10}):
                with patch('tests.conftest.pytest_blinkstick_monitor.save_config'):
                    with patch('tests.conftest.pytest_blinkstick_monitor.print_config'):
                        with patch('tests.conftest.pytest_blinkstick_monitor.log') as mock_log:
                            result = load_or_create_config()

                            assert result is not None
                            assert 'check_interval' in result


class TestBlacklistFunctions:
    """Test blacklist detection functions."""

    def test_is_blacklisted_exact_match(self):
        """Should match exact pattern."""
        assert is_blacklisted('mycontainer', ['mycontainer']) is True

    def test_is_blacklisted_glob_wildcard(self):
        """Should match glob wildcards."""
        assert is_blacklisted('lotus-sandbox-123', ['lotus-sandbox-*']) is True
        assert is_blacklisted('lotus-sandbox-abc', ['lotus-sandbox-*']) is True

    def test_is_blacklisted_no_match(self):
        """Should not match when pattern doesn't fit."""
        assert is_blacklisted('nginx', ['redis', 'postgres']) is False
        assert is_blacklisted('lotus-sandbox-1', ['mycontainer*']) is False

    def test_is_blacklisted_multiple_patterns(self):
        """Should return True if any pattern matches."""
        patterns = ['nginx', 'redis-*', 'postgres']
        assert is_blacklisted('redis-container', patterns) is True
        assert is_blacklisted('nginx', patterns) is True
        assert is_blacklisted('mysql', patterns) is False

    def test_is_blacklisted_empty_patterns(self):
        """Empty blacklist should not match anything."""
        assert is_blacklisted('anycontainer', []) is False
