"""
Import all blinkstick-monitor functions for testing.

This module wraps blinkstick-monitor.py to make it importable as a Python package.
"""

import sys
import os
from unittest.mock import MagicMock

# Get the directory containing this module
this_dir = os.path.dirname(os.path.abspath(__file__))

# Add parent directory to path so blinkstick is found
sys.path.insert(0, os.path.dirname(this_dir))

# Mock blinkstick hardware before import
sys.modules['blinkstick'] = MagicMock()
sys.modules['blinkstick.blinkstick'] = MagicMock()

# Create a namespace for exec
namespace = {
    '__name__': 'blinkstick_monitor',
    '__file__': os.path.join(os.path.dirname(this_dir), 'blinkstick-monitor.py'),
}

# Execute the monitor script to get its namespace
monitor_path = os.path.join(os.path.dirname(this_dir), 'blinkstick-monitor.py')
with open(monitor_path, 'r') as f:
    source = f.read()

exec(compile(source, monitor_path, 'exec'), namespace)

# Export all public names from namespace
for name, value in namespace.items():
    if not name.startswith('_'):
        globals()[name] = value
