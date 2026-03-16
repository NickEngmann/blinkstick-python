"""
Pytest configuration for blinkstick-monitor tests.
"""
import sys
import os
import importlib.util
import unittest.mock as mock

# Get the absolute path to the repo
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

# Mock hardware-dependent modules BEFORE importing blinkstick_monitor
# Create mock for blinkstick module
blinkstick_mock = mock.Mock()
blinkstick_mock.find_first.return_value = None
sys.modules['blinkstick'] = blinkstick_mock
sys.modules['blinkstick.blinkstick'] = blinkstick_mock
sys.modules['blinkstick._version'] = mock.Mock(__version__='1.2.0')

# Mock subprocess to prevent actual system calls
sys.modules['subprocess'] = mock.Mock()

# Load blinkstick_monitor directly from the file
spec = importlib.util.spec_from_file_location('blinkstick_monitor', os.path.join(repo_root, 'blinkstick-monitor.py'))
blinkstick_monitor = importlib.util.module_from_spec(spec)
sys.modules['blinkstick_monitor'] = blinkstick_monitor
spec.loader.exec_module(blinkstick_monitor)

# Make the module available for imports in tests
pytest_blinkstick_monitor = blinkstick_monitor
