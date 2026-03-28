# BlinkStick Python

Python interface to control BlinkStick USB LED devices.

More info: [blinkstick.com](http://www.blinkstick.com)

## Overview

This package provides:

1. **BlinkStick Library** — Python API and CLI for controlling BlinkStick USB LEDs
2. **Health Monitor** — Homelab system status indicator using BlinkStick LED colors

### BlinkStick Variants Supported

- BlinkStick (1 LED)
- BlinkStick Pro (1 LED)
- BlinkStick Strip (8 LEDs)
- BlinkStick Square (8 LEDs)
- BlinkStick Flex (32 LEDs)
- BlinkStick Nano (2 LEDs)

## Health Monitor

This fork includes a **homelab health monitoring daemon** that turns your BlinkStick into a system status indicator:

| Color  | Meaning |
|--------|---------|
| GREEN  | All systems healthy |
| RED    | Critical issue (container/service down, drive missing, mount gone) |
| YELLOW | Warning (disk filling up, high load) |
| BLUE   | Monitor starting up |

**What it monitors:** Docker containers, systemd services, block devices, mount points, disk usage, system load.

### Quick Install

```bash
# Clone the repo (or copy it to the machine)
git clone <repo-url> ~/blinkstick-python
cd ~/blinkstick-python

# Run the installer as root
sudo ./install-monitor.sh
```

The installer will:
1. Install system dependencies (libusb, pip, python3-dev)
2. Install udev rules for BlinkStick USB access
3. Install the blinkstick Python package from source
4. Install the monitor script to `/usr/local/bin/blinkstick-monitor`
5. Auto-detect the current system state as "healthy" baseline
6. Create and enable a systemd service

### Monitor Commands

```bash
# Check current health (no LED change)
sudo blinkstick-monitor --status

# Re-detect current state as the new "healthy" baseline
# Use this after adding containers, drives, services, or mounts
sudo blinkstick-monitor --reconfigure

# Or use the install script shortcut
sudo ./install-monitor.sh --reconfigure

# One-shot check (set LED and exit)
sudo blinkstick-monitor --check-once

# Reload config without restarting the service
sudo systemctl kill -s HUP blinkstick-monitor

# Restart the service
sudo systemctl restart blinkstick-monitor

# Tail logs
journalctl -u blinkstick-monitor -f

# Uninstall
sudo ./install-monitor.sh --uninstall
```

### Quiet Hours

LEDs turn off during a configurable time window (checks still run and log). Enabled by default: 23:00 - 07:00.

```bash
# Check quiet hours status
sudo blinkstick-monitor --quiet-hours status

# Enable with current times
sudo blinkstick-monitor --quiet-hours on

# Disable
sudo blinkstick-monitor --quiet-hours off

# Set custom window (e.g. 10pm to 6am)
sudo blinkstick-monitor --quiet-hours 22:00-06:00
```

After changing, reload the running service:
```bash
sudo systemctl kill -s HUP blinkstick-monitor
```

See [MONITOR.md](MONITOR.md) for full documentation including configuration options and troubleshooting.

## BlinkStick Library

### Requirements

- Python 3.6+
- libusb-1.0

### Installation

```bash
# From PyPI
pip install blinkstick

# From source (development)
pip install -e .
```

### Linux: libusb

```bash
# Debian/Ubuntu
sudo apt-get install libusb-1.0-0

# Fedora/RHEL
sudo dnf install libusb1
```

### Mac OS X: libusb

```bash
brew install libusb
```

If you get `ValueError: No backend available`:
```bash
sudo ln -s $(brew --prefix)/lib/libusb-* /usr/local/lib/
```

### Windows

Download and install [Python](https://www.python.org/downloads/) 3.x. Make sure "Add python.exe to Path" is selected during install.

```
pip install blinkstick
```

### Quick Start

```python
from blinkstick import blinkstick

stick = blinkstick.find_first()
stick.set_color(name="red")
stick.pulse(name="green")
```

### Command Line

```bash
blinkstick --pulse red
```

#### Command Line Options

```bash
# List all connected BlinkStick devices
blinkstick --info

# Set LED to a specific color
blinkstick --set-color red

# Set LED to a specific RGB value
blinkstick --set-color 255,0,0

# Pulse an LED with a color
blinkstick --pulse blue

# Set brightness/limit
blinkstick --limit 50

# Get information about LED
blinkstick --get-led

# Add udev rules for non-root access
sudo blinkstick --add-udev-rule
```

### Permissions (Linux/Mac)

If you get `Access denied (insufficient permissions)`:

```bash
# Add udev rule (Linux)
sudo blinkstick --add-udev-rule

# Or run with sudo
sudo blinkstick --set-color random
```

The `--add-udev-rule` option installs udev rules that allow non-root users to access BlinkStick devices. After running this, unplug and re-plug the device for the rules to take effect.

### Python API Reference

The `blinkstick` module provides the following functionality:

| Method | Description |
|--------|-------------|
| `find_first()` | Find the first connected BlinkStick device |
| `find_all()` | Find all connected BlinkStick devices |
| `set_color(channel=0, index=0, name="red")` | Set LED color by name or RGB values |
| `set_color_rgb(channel=0, index=0, red=255, green=0, blue=0)` | Set LED color by RGB values |
| `pulse(color, duration=1000)` | Create a pulsing effect |
| `morph(color1, color2, steps=10)` | Morph between two colors |
| `get_led_count()` | Get the number of LEDs on the device |
| `get_variant()` | Get the device variant (1=BlinkStick, 2=Pro, 3=Strip/Square, 4=Flex, 5=Nano) |
| `get_serial()` | Get the device serial number |
| `get_description()` | Get a human-readable device description |

## Maintainers

- Arvydas Juskevicius - [@arvydev](http://twitter.com/arvydev)
- Rob Berwick - [@robberwick](http://twitter.com/robberwick)
