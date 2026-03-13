# Agent Notes — BlinkStick Monitor

Developer context for AI agents and contributors working on this project.

## Project Layout

```
blinkstick-python/
├── blinkstick/              # BlinkStick Python library (upstream)
│   ├── __init__.py
│   ├── blinkstick.py        # Main library — find_first(), set_color(), etc.
│   └── _version.py
├── blinkstick-monitor.py    # Health monitoring daemon (custom)
├── install-monitor.sh       # One-command installer for the monitor
├── setup.py                 # Package setup (pip install -e .)
├── MONITOR.md               # User-facing monitor documentation
└── AGENT.md                 # This file
```

## BlinkStick Library Notes

- `blinkstick.find_first()` returns the first BlinkStick or `None`
- `set_color(channel, index, red, green, blue)` — index is the LED number (0-based)
- BlinkStick Nano has 2 LEDs (index 0 and 1) — must set both
- `get_led_count()` returns -1 for Nano variant; use `get_variant()` instead:
  - Variant 1 = BlinkStick (1 LED)
  - Variant 2 = Pro (1 LED)
  - Variant 3 = Strip/Square (8 LEDs)
  - Variant 4 = Flex (32 LEDs)
  - Variant 5 = Nano (2 LEDs)
- USB access requires root OR udev rules (installed by install-monitor.sh)
- `pyusb` is the USB backend; requires `libusb-1.0` system library

## Monitor Architecture

### Config Lifecycle
1. First install: `detect_config()` snapshots current state → `/etc/blinkstick-monitor.conf`
2. On boot: loads saved config (survives reboots)
3. `--reconfigure`: re-runs detection, overwrites config
4. SIGHUP: reloads config from disk without restart

### Check Priority
- Critical (RED): container down/missing, service down, block device gone, mount missing
- Warning (YELLOW): disk >85%, load > 2x CPUs, service removed
- OK (GREEN): everything passing

### Blacklists
- `container_blacklist_patterns`: glob patterns to exclude containers from detection (e.g. `"lotus-sandbox-*"`)
- `mount_blacklist_patterns`: glob patterns to exclude mounts (e.g. `"/mnt/nvme*"`)
- Both use `fnmatch` and persist across `--reconfigure`

### Quiet Hours
- `quiet_hours_enabled`, `quiet_hours_start`, `quiet_hours_end`
- LEDs turn off during the window; health checks still run and log
- Handles overnight spans (e.g. 23:00 -> 07:00)
- CLI: `--quiet-hours on|off|status|HH:MM-HH:MM`

### Resilience Features
- Boot delay (default 30s) — waits for docker/mounts after reboot
- BlinkStick reconnection — retries if USB device temporarily disconnected
- Service auto-restart (systemd Restart=always, RestartSec=5)
- Graceful SIGTERM handling — turns off LEDs on shutdown
- Config validation — merges with defaults so missing keys don't crash

## Install Script

`install-monitor.sh` is idempotent — safe to re-run. Handles:
- pip, libusb, udev rules, blinkstick package
- Detects package manager: apt, dnf, pacman, apk
- Auto-generates systemd service with correct docker dependency
- `--reconfigure` flag re-detects baseline
- `--uninstall` cleans up (preserves config)

## Key Files on Target Systems

| Path                              | Purpose                    |
|-----------------------------------|----------------------------|
| `/usr/local/bin/blinkstick-monitor` | Monitor script             |
| `/etc/blinkstick-monitor.conf`    | Saved healthy baseline     |
| `/etc/systemd/system/blinkstick-monitor.service` | systemd unit |
| `/etc/udev/rules.d/85-blinkstick.rules` | USB permissions     |

## Common Operations

```bash
# Test the monitor manually
sudo blinkstick-monitor --status
sudo blinkstick-monitor --check-once

# Update baseline after infra changes
sudo blinkstick-monitor --reconfigure && sudo systemctl restart blinkstick-monitor

# Reload config without restart
sudo systemctl kill -s HUP blinkstick-monitor

# Debug
journalctl -u blinkstick-monitor -f
```

## Gotchas

- `findmnt --raw` doesn't work on all systems — use `findmnt -n -l` without `--raw`
- `findmnt` output is space-padded; use `.strip()` or `rsplit(None, 1)` when parsing
- Docker containers detected with `docker ps` (running only), not `docker ps -a`
- User services detected by looking for regular files (not symlinks) in `/etc/systemd/system/`
- `is_blacklisted()` uses `fnmatch.fnmatch()` for glob matching (supports `*`, `?`, `[seq]`)
- The service runs as root (needed for USB + docker access)
- Color values are intentionally dim (64 max, not 255) to avoid blinding in dark server rooms
