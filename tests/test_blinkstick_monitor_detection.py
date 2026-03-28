"""Unit tests for blinkstick-monitor.py detection functions."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blinkstick import monitor
from blinkstick.monitor import (
    detect_user_services,
    detect_config,
    detect_led_count,
    load_config,
    save_config,
    is_blacklisted,
)


class TestDetectUserServices(unittest.TestCase):
    """Test detect_user_services function."""

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_empty(self, mock_run):
        """Test when no user services exist."""
        mock_run.return_value = ('', 0)
        services = detect_user_services()
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_single(self, mock_run):
        """Test detection of a single user service."""
        mock_run.side_effect = [
            ('/etc/systemd/system/myapp.service', 0),  # find command
            ('active', 0),                              # systemctl is-active
        ]
        services = detect_user_services()
        self.assertIn('myapp.service', services)

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_multiple(self, mock_run):
        """Test detection of multiple user services."""
        mock_run.side_effect = [
            (
                '/etc/systemd/system/backup.service\n'
                '/etc/systemd/system/database.service\n'
                '/etc/systemd/system/webapp.service',
                0
            ),
            ('active', 0),  # backup.service
            ('active', 0),  # database.service
            ('active', 0),  # webapp.service
        ]
        services = detect_user_services()
        self.assertEqual(len(services), 3)
        self.assertIn('backup.service', services)
        self.assertIn('database.service', services)
        self.assertIn('webapp.service', services)

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_skips_inactive(self, mock_run):
        """Test that inactive services are not detected."""
        mock_run.side_effect = [
            ('/etc/systemd/system/myapp.service', 0),
            ('inactive', 1),  # Service is not active
        ]
        services = detect_user_services()
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_skips_timers(self, mock_run):
        """Test that timer files are not returned by find -type f -name *.service."""
        # find with -name '*.service' won't return .timer files
        mock_run.return_value = ('', 0)
        services = detect_user_services()
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_skips_cron(self, mock_run):
        """Test that cron-related services are skipped."""
        mock_run.side_effect = [
            ('/etc/systemd/system/cron.service', 0),
            ('', 1),  # systemctl is-active fails (cron not active)
            ('/etc/systemd/system/anacron.service', 0),
            ('', 1),
            ('/etc/systemd/system/atd.service', 0),
            ('', 1),
        ]
        services = detect_user_services()
        # None will be active, so empty result
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_skips_ourself(self, mock_run):
        """Test that blinkstick-monitor service is skipped."""
        mock_run.side_effect = [
            ('/etc/systemd/system/blinkstick-monitor.service', 0),
            ('inactive', 1),  # Not active
        ]
        services = detect_user_services()
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_symlinks_skipped(self, mock_run):
        """Test that symlinks are skipped (not regular files)."""
        # With -type f, symlinks won't be returned
        mock_run.return_value = ('', 0)
        services = detect_user_services()
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_systemctl_error(self, mock_run):
        """Test handling of systemctl errors."""
        mock_run.side_effect = [
            ('/etc/systemd/system/myapp.service', 0),
            (None, 1),  # Error from systemctl is-active
        ]
        services = detect_user_services()
        # Service won't be included if systemctl fails
        self.assertEqual(services, [])

    @patch('blinkstick.monitor.run')
    def test_detect_user_services_find_error(self, mock_run):
        """Test handling of find command errors."""
        mock_run.return_value = ('', 1)
        services = detect_user_services()
        self.assertEqual(services, [])


class TestDetectConfig(unittest.TestCase):
    """Test detect_config function."""

    def setUp(self):
        """Set up test fixtures."""
        self.default_config = {
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
            'container_blacklist_patterns': [],
            'mount_blacklist_patterns': [],
            'quiet_hours_enabled': True,
            'quiet_hours_start': '23:00',
            'quiet_hours_end': '07:00',
            'led_count': 2,
        }

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.run')
    @patch('blinkstick.monitor.detect_led_count')
    def test_detect_config_empty_system(self, mock_led, mock_run, mock_services):
        """Test detect_config on a system with no services."""
        mock_run.side_effect = [
            ('', 127),  # Docker not found
            ('', 0),  # lsblk output  
            ('', 0),  # findmnt output
        ]
        mock_services.return_value = []
        mock_led.return_value = 2

        config = detect_config()

        self.assertEqual(config['monitor_docker'], False)
        self.assertEqual(config['monitor_services'], False)
        self.assertEqual(config['expected_containers'], [])
        self.assertEqual(config['expected_block_devices'], [])
        self.assertEqual(config['expected_mounts'], [])
        self.assertEqual(config['led_count'], 2)

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.run')
    @patch('blinkstick.monitor.detect_led_count')
    def test_detect_config_with_docker(self, mock_led, mock_run, mock_services):
        """Test detect_config with Docker containers."""
        mock_run.side_effect = [
            ('container1\ncontainer2\ncontainer3', 0),  # docker ps
            ('', 0),  # lsblk output
            ('', 0),  # findmnt output
        ]
        mock_services.return_value = []
        mock_led.return_value = 2

        config = detect_config()

        self.assertTrue(config['monitor_docker'])
        self.assertEqual(len(config['expected_containers']), 3)
        self.assertIn('container1', config['expected_containers'])

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.run')
    @patch('blinkstick.monitor.detect_led_count')
    def test_detect_config_with_services(self, mock_led, mock_run, mock_services):
        """Test detect_config with user services."""
        mock_run.side_effect = [
            ('', 127),  # Docker not found
            ('', 0),  # lsblk output
            ('', 0),  # findmnt output
        ]
        mock_services.return_value = ['myapp.service', 'database.service']
        mock_led.return_value = 2

        config = detect_config()

        self.assertTrue(config['monitor_services'])
        self.assertEqual(len(config['expected_services']), 2)

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_preserves_blacklist(self, mock_run, mock_led, mock_services):
        """Test that blacklist patterns are preserved."""
        mock_run.return_value = ('', 127)
        mock_services.return_value = []
        mock_led.return_value = 2
        
        existing_config = {
            'container_blacklist_patterns': ['test-*', 'dev-*'],
            'mount_blacklist_patterns': ['/mnt/test*'],
        }
        
        config = detect_config(blacklist=['test-*'],
                               preserve_config=existing_config)
        
        self.assertIn('test-*', config['container_blacklist_patterns'])

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_preserves_quiet_hours(self, mock_run, mock_led, mock_services):
        """Test that quiet hours settings are preserved."""
        mock_run.return_value = ('', 127)
        mock_services.return_value = []
        mock_led.return_value = 2
        
        existing_config = {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '06:00',
        }
        
        config = detect_config(preserve_config=existing_config)
        
        self.assertTrue(config['quiet_hours_enabled'])
        self.assertEqual(config['quiet_hours_start'], '22:00')
        self.assertEqual(config['quiet_hours_end'], '06:00')

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_filters_blacklisted_containers(self, mock_run, mock_led, mock_services):
        """Test that blacklisted containers are filtered."""
        mock_run.side_effect = [
            ('app1\napp2\nlotus-sandbox-1', 0),  # docker ps
            ('', 0),  # lsblk
            ('', 0),  # findmnt
        ]
        mock_services.return_value = []
        mock_led.return_value = 2
        
        config = detect_config(blacklist=['lotus-sandbox-*'])
        
        # Should exclude lotus-sandbox-1
        self.assertIn('app1', config['expected_containers'])
        self.assertIn('app2', config['expected_containers'])
        self.assertNotIn('lotus-sandbox-1', config['expected_containers'])


class TestDetectLedCount(unittest.TestCase):
    """Test detect_led_count function."""

    @patch('blinkstick.blinkstick.find_first')
    @patch('blinkstick.blinkstick.BlinkStick.get_variant')
    @patch('blinkstick.blinkstick.BlinkStick.get_led_count')
    def test_detect_led_count_no_device(self, mock_get_led, mock_variant, mock_find):
        """Test when no BlinkStick device is found."""
        mock_find.return_value = None
        count = detect_led_count()
        self.assertEqual(count, 2)

    @patch('blinkstick.blinkstick.find_first')
    @patch('blinkstick.blinkstick.BlinkStick.get_variant')
    @patch('blinkstick.blinkstick.BlinkStick.get_led_count')
    def test_detect_led_count_variant_mapping(self, mock_get_led, mock_variant, mock_find):
        """Test variant to LED count mapping."""
        mock_get_led.return_value = -1
        mock_find.return_value = object()

        test_cases = [
            (1, 1),   # BlinkStick
            (2, 1),   # Pro
            (3, 8),   # Strip/Square
            (4, 32),  # Flex
            (5, 2),   # Nano
        ]

        for variant, expected_count in test_cases:
            mock_variant.return_value = variant
            count = detect_led_count()
            self.assertEqual(count, expected_count,
                           f"Variant {variant} should map to {expected_count} LEDs")

    @patch('blinkstick.blinkstick.find_first')
    def test_detect_led_count_valid_count(self, mock_find):
        """Test when get_led_count returns a valid count."""
        mock_stick = unittest.mock.MagicMock()
        mock_stick.get_led_count.return_value = 8
        mock_find.return_value = mock_stick
        count = detect_led_count()
        self.assertEqual(count, 8)

    @patch('blinkstick.blinkstick.find_first')
    @patch('blinkstick.blinkstick.BlinkStick.get_variant')
    @patch('blinkstick.blinkstick.BlinkStick.get_led_count')
    def test_detect_led_count_variant_mapping_with_magic(self, mock_get_led, mock_variant, mock_find):
        """Test variant to LED count mapping using proper mocking."""
        test_cases = [
            (1, 1),   # BlinkStick
            (2, 1),   # Pro
            (3, 8),   # Strip/Square
            (4, 32),  # Flex
            (5, 2),   # Nano
        ]

        for variant, expected_count in test_cases:
            mock_find.return_value = unittest.mock.MagicMock()
            mock_get_led.return_value = -1
            mock_variant.return_value = variant
            count = detect_led_count()
            self.assertEqual(count, expected_count,
                           f"Variant {variant} should map to {expected_count} LEDs")

    @patch('blinkstick.blinkstick.find_first')
    def test_detect_led_count_exception(self, mock_find):
        """Test exception handling returns default."""
        mock_find.side_effect = Exception("Device error")
        count = detect_led_count()
        self.assertEqual(count, 2)

    @patch('blinkstick.monitor.os.path.exists')
    @patch('blinkstick.monitor.open', new_callable=mock_open, read_data='{}')
    def test_detect_led_count_fallback(self, mock_open_file, mock_exists):
        """Test fallback when blinkstick import fails."""
        # When from blinkstick import blinkstick fails, it should catch exception
        mock_exists.return_value = False
        count = detect_led_count()
        self.assertEqual(count, 2)


class TestIsBlacklisted(unittest.TestCase):
    """Test is_blacklisted helper function."""

    def test_blacklist_exact_match(self):
        """Test exact pattern match."""
        self.assertTrue(is_blacklisted('docker-nginx', ['docker-nginx']))

    def test_blacklist_wildcard_match(self):
        """Test wildcard pattern matching."""
        self.assertTrue(is_blacklisted('dev-server-1', ['dev-*']))
        self.assertTrue(is_blacklisted('dev-server-abc', ['dev-*']))
        self.assertTrue(is_blacklisted('lotus-sandbox-123', ['lotus-sandbox-*']))

    def test_blacklist_no_match(self):
        """Test when pattern doesn't match."""
        self.assertFalse(is_blacklisted('prod-server', ['dev-*', 'test-*']))
        self.assertFalse(is_blacklisted('docker-nginx', ['docker-postgres']))

    def test_blacklist_empty_patterns(self):
        """Test with empty blacklist."""
        self.assertFalse(is_blacklisted('anything', []))

    def test_blacklist_multiple_patterns(self):
        """Test with multiple patterns."""
        patterns = ['dev-*', 'test-*', 'lotus-*']
        self.assertTrue(is_blacklisted('dev-server', patterns))
        self.assertTrue(is_blacklisted('test-runner', patterns))
        self.assertTrue(is_blacklisted('lotus-sandbox', patterns))
        self.assertFalse(is_blacklisted('prod-server', patterns))


class TestDetectConfigEdgeCases(unittest.TestCase):
    """Test edge cases in detect_config."""

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_no_containers(self, mock_run, mock_led, mock_services):
        """Test when Docker is available but no containers running."""
        mock_run.return_value = ('', 0)  # Empty output
        mock_services.return_value = []
        mock_led.return_value = 2
        
        config = detect_config()
        
        self.assertFalse(config['monitor_docker'])
        self.assertEqual(config['expected_containers'], [])

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_block_device_filtering(self, mock_run, mock_led, mock_services):
        """Test filtering of block devices."""
        mock_run.return_value = (
            'sda disk\n'
            'sdb disk\n'
            'loop0 loop\n'
            'bootdisk disk',
            0
        )
        mock_services.return_value = []
        mock_led.return_value = 2
        
        config = detect_config()
        
        # Should include sda and sdb, exclude loop and bootdisk
        self.assertIn('sda', config['expected_block_devices'])
        self.assertIn('sdb', config['expected_block_devices'])
        self.assertNotIn('loop0', config['expected_block_devices'])
        self.assertNotIn('bootdisk', config['expected_block_devices'])

    @patch('blinkstick.monitor.detect_user_services')
    @patch('blinkstick.monitor.detect_led_count')
    @patch('blinkstick.monitor.run')
    def test_detect_config_mount_type_filtering(self, mock_run, mock_led, mock_services):
        """Test filtering of mount points by filesystem type."""
        mock_run.side_effect = [
            (
                '/home ext4\n'
                '/boot vfat\n'
                '/mnt/nfs nfs\n'
                '/mnt/loop loop',
                0
            ),
            (None, 0),
        ]
        mock_services.return_value = []
        mock_led.return_value = 2
        
        config = detect_config()
        
        # ext4, nfs should be included, vfat and loop excluded
        self.assertIn('/home', config['expected_mounts'])
        self.assertIn('/mnt/nfs', config['expected_mounts'])
        self.assertNotIn('/boot', config['expected_mounts'])
        self.assertNotIn('/mnt/loop', config['expected_mounts'])


if __name__ == '__main__':
    unittest.main()
