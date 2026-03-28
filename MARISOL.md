# MARISOL.md - Pipeline Context for blinkstick-python

## Repository Information
- **Project**: blinkstick-python - Python interface for BlinkStick USB LED devices
- **Version**: 1.2.0 (from blinkstick/_version.py line 1)
- **Languages**: Python 3
- **Primary Dependencies**: pyusb>=1.0.0 (from setup.py line 37), setuptools
- **License**: See LICENSE.txt
- **Repository Root**: /repo

## Dependencies

### Runtime Dependencies
| Package | Version | Source |
|---------|---------|--------|
| pyusb | >=1.0.0 | setup.py line 37 |
| setuptools | - | setup.py line 29 |

### Development Dependencies
| Package | Version | Source |
|---------|---------|--------|
| pytest | - | Not explicitly defined |

### System Dependencies
| Package | Purpose |
|---------|---------|
| libusb-1.0-0 | USB communication |
| python3-dev | Header files for pyusb |

## Project Structure
```
/repo/
├── blinkstick/               # Main library package
│   ├── __init__.py
│   ├── _version.py          # Version: 1.2.0
│   └── blinkstick.py
├── bin/
│   └── blinkstick           # Command-line tool
├── blinkstick-monitor.py    # Health monitoring daemon
├── install-monitor.sh       # Installer script
├── setup.py                 # Package configuration
└── tests/                   # Test files (if any)
```

## Pipeline Context
- Docker image: python:3.12-slim
- Python version: 3.12.3 (verified)
- Build command: pip install -e .[dev,test]
- Test command: pytest tests/ -v

## Pipeline History
- *2026-03-19* - Implemented comprehensive tests for blinkstick-python, all 145 tests pass covering health monitoring daemon and USB device interface functionality
- *2026-03-19* - All 145 tests pass successfully after implementation of blinkstick-monitor-detection tests
- *2026-03-27* - Pipeline history notes incomplete data

## Notes
- Health monitor monitors: Docker containers, systemd services, block devices, mount points, disk usage, system load
- LED colors: GREEN=healthy, RED=critical, YELLOW=warning, BLUE=starting, OFF=quiet hours
- Configuration: /etc/blinkstick-monitor.conf (auto-generated JSON)
- Quiet hours: Default 23:00-07:00, configurable via CLI or config file
- udev rules: Installed at /etc/udev/rules.d/85-blinkstick.rules for USB access
- Tested platforms: Ubuntu/Debian, Fedora/RHEL/CentOS, Arch Linux, Alpine
- BlinkStick variants: Nano (2 LEDs), Pro (1 LED), Strip (8 LEDs), Square (8 LEDs), Flex (32 LEDs)
