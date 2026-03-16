"""
Tests for color mapping utilities and LED color determination logic.
"""
import pytest
import tests.conftest as fixtures

determine_color = fixtures.pytest_blinkstick_monitor.determine_color
COLOR_GREEN = fixtures.pytest_blinkstick_monitor.COLOR_GREEN
COLOR_RED = fixtures.pytest_blinkstick_monitor.COLOR_RED
COLOR_YELLOW = fixtures.pytest_blinkstick_monitor.COLOR_YELLOW
COLOR_OFF = fixtures.pytest_blinkstick_monitor.COLOR_OFF