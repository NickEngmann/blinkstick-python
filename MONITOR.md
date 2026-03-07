# BlinkStick Health Monitor

A homelab monitoring daemon that uses a BlinkStick USB LED to show system health at a glance.

## LED Color Guide

| Color    | Meaning                                                          |
|----------|------------------------------------------------------------------|
| GREEN    | All systems healthy                                              |
| RED      | Critical issue — container down, drive missing, mount gone       |
| YELLOW   | Warning — disk filling up (>85%), high system load               |
| BLUE     | Monitor is starting up / initializing                            |
| OFF      | Monitor is not running                                           |

## Quick Install

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
5. Auto-detect the current system state (docker containers, drives, mounts) as "healthy"
6. Create and enable a systemd service

## What It Monitors

- **Docker containers** — detects all running containers at install time; alerts if any stop or crash
- **Block devices** — NVMe, SSD, HDD; alerts if a drive disappears
- **Mount points** — ext4, xfs, btrfs, zfs, nfs, mergerfs, etc.; alerts if a mount is lost
- **Disk usage** — warns when any filesystem exceeds 85% (configurable)
- **System load** — warns when 1-minute load average exceeds 2x CPU count (configurable)

## Commands

```bash
# Check current health (no LED change)
sudo blinkstick-monitor --status

# Re-detect current state as the new "healthy" baseline
# Use this after adding containers, drives, or mounts
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

## Configuration

Config is stored at `/etc/blinkstick-monitor.conf` (JSON). It's auto-generated on first install.

Example:
```json
{
  "check_interval": 10,
  "disk_warn_percent": 85,
  "load_warn_multiplier": 2.0,
  "boot_delay": 30,
  "monitor_docker": true,
  "expected_containers": [
    "my-app",
    "my-db",
    "my-redis"
  ],
  "expected_block_devices": [
    "sda",
    "nvme0n1"
  ],
  "expected_mounts": [
    "/",
    "/mnt/data",
    "/mnt/backup"
  ],
  "led_count": 2
}
```

### Config Options

| Key                    | Default | Description                                       |
|------------------------|---------|---------------------------------------------------|
| `check_interval`       | 10      | Seconds between health checks                     |
| `disk_warn_percent`    | 85      | Disk usage % threshold for yellow warning          |
| `load_warn_multiplier` | 2.0     | Load average threshold = CPU count * this value    |
| `boot_delay`           | 30      | Seconds to wait after boot before first check      |
| `monitor_docker`       | auto    | Whether to check docker containers                 |
| `expected_containers`  | auto    | List of container names that should be running     |
| `expected_block_devices` | auto  | Block device names that should be present          |
| `expected_mounts`      | auto    | Mount point paths that should be mounted           |
| `led_count`            | auto    | Number of LEDs on the BlinkStick                   |

## Updating the Baseline

When you change your setup (add containers, add a drive, etc.):

```bash
# Make sure the system is in a good state, then:
sudo blinkstick-monitor --reconfigure
sudo systemctl restart blinkstick-monitor
```

Or equivalently:
```bash
sudo ./install-monitor.sh --reconfigure
```

This re-snapshots the current state as "healthy" and saves it.

## Deploying to Multiple Machines

1. Copy the repo to each machine
2. Run `sudo ./install-monitor.sh`
3. The installer auto-detects what's on each machine — no manual config needed

The same script works on machines with:
- Docker containers only
- External drives only
- Full AI agent stacks
- Any combination

## Supported Platforms

- Ubuntu / Debian
- Fedora / RHEL / CentOS (dnf)
- Arch Linux (pacman)
- Alpine (apk)

## BlinkStick Variants

Tested with BlinkStick Nano. Should work with all variants:
- BlinkStick (1 LED)
- BlinkStick Pro (1 LED)
- BlinkStick Strip (8 LEDs)
- BlinkStick Square (8 LEDs)
- BlinkStick Flex (32 LEDs)
- BlinkStick Nano (2 LEDs)

## Troubleshooting

**BlinkStick not detected:**
- Unplug and re-plug the device (triggers udev rules)
- Check `lsusb | grep 20a0`
- Check `journalctl -u blinkstick-monitor -n 30`

**Service won't start:**
- Check logs: `journalctl -u blinkstick-monitor -n 50`
- Test manually: `sudo blinkstick-monitor --check-once`

**False alerts after reboot:**
- The monitor waits 30s after boot (configurable via `boot_delay`)
- If docker takes longer to start, increase `boot_delay` in the config
