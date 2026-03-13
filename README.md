# BlinkStick Python

Python interface to control BlinkStick USB LED devices.

More info: [blinkstick.com](http://www.blinkstick.com)

## Health Monitor

This fork includes a **homelab health monitoring daemon** that turns your BlinkStick into a system status indicator:

| Color  | Meaning |
|--------|---------|
| GREEN  | All systems healthy |
| RED    | Critical issue (container/service down, drive missing, mount gone) |
| YELLOW | Warning (disk filling up, high load) |
| BLUE   | Monitor starting up |

**What it monitors:** Docker containers, systemd services, block devices, mount points, disk usage, system load.

```bash
# Install everything (deps, monitor, systemd service)
sudo ./install-monitor.sh

# Update on existing machines
git pull && sudo ./install-monitor.sh
```

See [MONITOR.md](MONITOR.md) for full documentation.

## BlinkStick Library

### Requirements

- Python 3
- libusb

### Installation

```bash
# From PyPI
pip install blinkstick

# From source
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

### Permissions (Linux/Mac)

If you get `Access denied (insufficient permissions)`:

```bash
# Add udev rule (Linux)
sudo blinkstick --add-udev-rule

# Or run with sudo
sudo blinkstick --set-color random
```

## Resources

- [API reference](https://arvydas.github.io/blinkstick-python)
- [Code examples](https://github.com/arvydas/blinkstick-python/wiki)

## Maintainers

- Arvydas Juskevicius - [@arvydev](http://twitter.com/arvydev)
- Rob Berwick - [@robberwick](http://twitter.com/robberwick)
