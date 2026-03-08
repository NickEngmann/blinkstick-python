#!/usr/bin/env python3
"""
BlinkStick Health Monitor — Homelab Edition

Monitors system health and reflects status on a BlinkStick USB LED.

Checks:
  - Docker containers (expected ones running)
  - Systemd services (user-created .service units)
  - Block devices present (NVMe, SSD, HDD)
  - Mount points accessible
  - Disk usage thresholds
  - System load average

Color scheme:
  GREEN  = all healthy
  RED    = critical (container down, drive missing, mount gone)
  YELLOW = warning (disk filling up, high load)
  BLUE (pulse on start) = monitor is initializing

Usage:
  blinkstick-monitor                  # run monitor (normal systemd mode)
  blinkstick-monitor --reconfigure    # re-detect current state as "good" and save config
  blinkstick-monitor --status         # one-shot: print current health and exit
  blinkstick-monitor --check-once     # one-shot: check, set LED, exit

Config: /etc/blinkstick-monitor.conf (JSON, auto-generated, editable)
Send SIGHUP to the running service to reload config without restart:
  systemctl kill -s HUP blinkstick-monitor
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('blinkstick-monitor')

CONFIG_PATH = '/etc/blinkstick-monitor.conf'

# --- Color definitions (R, G, B) — intentionally dim to not blind you ---
COLOR_GREEN  = (0, 64, 0)
COLOR_RED    = (64, 0, 0)
COLOR_YELLOW = (64, 40, 0)
COLOR_BLUE   = (0, 0, 64)
COLOR_OFF    = (0, 0, 0)

DEFAULT_CONFIG = {
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
    'led_count': 2,
}

# Global for SIGHUP reload
_reload_requested = False


def request_reload(signum, frame):
    global _reload_requested
    _reload_requested = True
    log.info('SIGHUP received — will reload config on next cycle')


def run(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.returncode
    except FileNotFoundError:
        return '', 127
    except subprocess.TimeoutExpired:
        return 'command timed out', 1
    except Exception as e:
        return str(e), 1


def detect_user_services():
    """Find user-created systemd services that are currently active.

    Only considers regular .service files in /etc/systemd/system/ (not symlinks,
    which are typically distro-managed aliases like dbus-org.*.service).
    Skips timers, cron-like units, and the blinkstick monitor itself.
    """
    services = []
    skip_patterns = {'blinkstick-monitor', 'cron', 'anacron', 'atd'}

    # List regular .service files (not symlinks) the user created
    # Symlinks in /etc/systemd/system/ are distro-managed (dbus aliases, display-manager, etc.)
    out, rc = run(['find', '/etc/systemd/system/', '-maxdepth', '1',
                   '-name', '*.service', '-type', 'f'])
    if rc != 0:
        return services

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        unit_name = os.path.basename(line)

        # Skip cron-related and ourselves
        base = unit_name.replace('.service', '')
        if any(skip in base.lower() for skip in skip_patterns):
            continue

        # Only include if currently active
        _, active_rc = run(['systemctl', 'is-active', '--quiet', unit_name])
        if active_rc == 0:
            services.append(unit_name)

    return services


def detect_config():
    """Snapshot current system state as the 'known good' baseline."""
    config = dict(DEFAULT_CONFIG)

    # Docker: only track containers currently in "Up" state
    out, rc = run(['docker', 'ps', '--format', '{{.Names}}'])
    if rc == 0 and out:
        config['monitor_docker'] = True
        config['expected_containers'] = sorted(out.splitlines())
    elif rc == 127:
        log.info('Docker not installed — skipping container monitoring')

    # Systemd services: user-created .service units in /etc/systemd/system/
    # Excludes timers, cron-like units, and the blinkstick monitor itself
    user_services = detect_user_services()
    if user_services:
        config['monitor_services'] = True
        config['expected_services'] = sorted(user_services)

    # Block devices: real disks only (skip loops and boot partitions)
    out, rc = run(['lsblk', '-d', '-n', '-o', 'NAME,TYPE'])
    if rc == 0:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'disk':
                name = parts[0]
                if name.startswith('loop') or 'boot' in name:
                    continue
                config['expected_block_devices'].append(name)

    # Mounts: parse findmnt output (fstype is right-aligned, use rsplit)
    out, rc = run(['findmnt', '-n', '-l', '-o', 'TARGET,FSTYPE'])
    if rc == 0:
        real_fstypes = {'ext4', 'xfs', 'btrfs', 'zfs', 'ntfs', 'vfat',
                        'fuse.mergerfs', 'nfs', 'nfs4', 'cifs', 'f2fs'}
        for line in out.splitlines():
            # findmnt pads with spaces; split from right to get fstype
            parts = line.rsplit(None, 1)
            if len(parts) == 2:
                target = parts[0].strip()
                fstype = parts[1].strip()
                if fstype in real_fstypes:
                    config['expected_mounts'].append(target)

    # Auto-detect LED count by probing
    config['led_count'] = detect_led_count()

    return config


def detect_led_count():
    """Figure out how many LEDs the BlinkStick has based on variant."""
    try:
        from blinkstick import blinkstick
        stick = blinkstick.find_first()
        if stick is None:
            return 2
        # Variant-based LED count (get_led_count() returns -1 for some models)
        # Variants: 1=BlinkStick, 2=Pro, 3=Strip/Square, 4=Flex, 5=Nano
        variant = stick.get_variant()
        variant_leds = {1: 1, 2: 1, 3: 8, 4: 32, 5: 2}
        count = stick.get_led_count()
        if count > 0:
            return count
        return variant_leds.get(variant, 2)
    except Exception:
        return 2


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    log.info(f'Config saved to {CONFIG_PATH}')


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULT_CONFIG)
        merged.update(config)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        log.error(f'Failed to load config: {e}')
        return None


def load_or_create_config():
    config = load_config()
    if config is not None:
        log.info(f'Loaded config from {CONFIG_PATH}')
        return config

    log.info('No config found — auto-detecting current state as baseline')
    config = detect_config()
    save_config(config)
    print_config(config)
    return config


def print_config(config):
    log.info('Current configuration:')
    for key, val in config.items():
        if isinstance(val, list):
            log.info(f'  {key}: {", ".join(val) if val else "(none)"}')
        else:
            log.info(f'  {key}: {val}')


# ---- Health checks ----

def check_docker(config):
    issues = []
    if not config.get('monitor_docker'):
        return issues

    out, rc = run(['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}'])
    if rc != 0:
        issues.append(('critical', 'Cannot reach Docker daemon'))
        return issues

    running_containers = {}
    for line in out.splitlines():
        parts = line.split('\t', 1)
        if len(parts) == 2:
            running_containers[parts[0]] = parts[1]

    for name in config.get('expected_containers', []):
        if name not in running_containers:
            issues.append(('critical', f'Container missing: {name}'))
        else:
            status = running_containers[name]
            if 'Up' not in status:
                issues.append(('critical', f'Container down: {name} ({status})'))
            elif 'unhealthy' in status.lower():
                issues.append(('warning', f'Container unhealthy: {name}'))

    return issues


def check_services(config):
    issues = []
    if not config.get('monitor_services'):
        return issues

    for unit in config.get('expected_services', []):
        _, rc = run(['systemctl', 'is-active', '--quiet', unit])
        if rc != 0:
            # Check if the unit still exists (may have been intentionally removed)
            _, exists_rc = run(['systemctl', 'cat', unit])
            if exists_rc != 0:
                issues.append(('warning', f'Service removed: {unit}'))
            else:
                issues.append(('critical', f'Service down: {unit}'))

    return issues


def check_block_devices(config):
    issues = []
    out, rc = run(['lsblk', '-d', '-n', '-o', 'NAME'])
    if rc != 0:
        issues.append(('warning', 'Cannot run lsblk'))
        return issues

    present = set(line.strip() for line in out.splitlines())
    for dev in config.get('expected_block_devices', []):
        if dev not in present:
            issues.append(('critical', f'Block device missing: {dev}'))

    return issues


def check_mounts(config):
    issues = []
    out, rc = run(['findmnt', '-n', '-l', '-o', 'TARGET'])
    if rc != 0:
        issues.append(('warning', 'Cannot run findmnt'))
        return issues

    mounted = set(line.strip() for line in out.splitlines())
    for mp in config.get('expected_mounts', []):
        if mp not in mounted:
            issues.append(('critical', f'Mount missing: {mp}'))

    return issues


def check_disk_usage(config):
    issues = []
    threshold = config.get('disk_warn_percent', 85)
    out, rc = run(['df', '--output=pcent,target', '-x', 'tmpfs', '-x', 'devtmpfs',
                   '-x', 'squashfs', '-x', 'overlay', '-x', 'efivarfs'])
    if rc != 0:
        return issues

    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        # percent is first token, rest is mount target (may have spaces)
        parts = line.split(None, 1)
        if len(parts) >= 2:
            try:
                pct = int(parts[0].replace('%', ''))
                target = parts[1]
                if pct >= threshold:
                    issues.append(('warning', f'Disk {target} at {pct}%'))
            except ValueError:
                pass

    return issues


def check_load(config):
    issues = []
    cpu_count = os.cpu_count() or 1
    threshold = cpu_count * config.get('load_warn_multiplier', 2.0)
    try:
        load1, _, _ = os.getloadavg()
        if load1 > threshold:
            issues.append(('warning', f'High load: {load1:.1f} (threshold {threshold:.1f})'))
    except OSError:
        pass
    return issues


def run_all_checks(config):
    all_issues = []
    all_issues.extend(check_docker(config))
    all_issues.extend(check_services(config))
    all_issues.extend(check_block_devices(config))
    all_issues.extend(check_mounts(config))
    all_issues.extend(check_disk_usage(config))
    all_issues.extend(check_load(config))
    return all_issues


# ---- BlinkStick control ----

_stick = None


def get_stick():
    global _stick
    try:
        from blinkstick import blinkstick
        if _stick is not None:
            # Verify it's still connected
            try:
                _stick.get_serial()
                return _stick
            except Exception:
                _stick = None

        _stick = blinkstick.find_first()
        return _stick
    except Exception as e:
        log.error(f'BlinkStick error: {e}')
        return None


def set_blinkstick_color(r, g, b, led_count=2):
    stick = get_stick()
    if stick is None:
        log.error('No BlinkStick found')
        return False
    try:
        for i in range(led_count):
            stick.set_color(channel=0, index=i, red=r, green=g, blue=b)
        return True
    except Exception as e:
        log.error(f'Failed to set BlinkStick color: {e}')
        global _stick
        _stick = None
        return False


# ---- Main loops ----

def determine_color(issues):
    criticals = [i for i in issues if i[0] == 'critical']
    warnings = [i for i in issues if i[0] == 'warning']

    if criticals:
        for _, msg in criticals:
            log.warning(f'CRITICAL: {msg}')
        return COLOR_RED, 'RED'
    elif warnings:
        for _, msg in warnings:
            log.info(f'WARNING: {msg}')
        return COLOR_YELLOW, 'YELLOW'
    else:
        return COLOR_GREEN, 'GREEN'


def cmd_status(config):
    """One-shot: print health status and exit."""
    issues = run_all_checks(config)
    if not issues:
        print('STATUS: ALL OK')
        return 0

    exit_code = 0
    for severity, msg in issues:
        tag = 'CRITICAL' if severity == 'critical' else 'WARNING'
        print(f'  [{tag}] {msg}')
        if severity == 'critical':
            exit_code = 2
        elif exit_code == 0:
            exit_code = 1
    return exit_code


def cmd_check_once(config):
    """One-shot: run checks, set LED color, exit."""
    issues = run_all_checks(config)
    color, label = determine_color(issues)
    led_count = config.get('led_count', 2)
    r, g, b = color
    log.info(f'Setting BlinkStick to {label}')
    set_blinkstick_color(r, g, b, led_count)
    return 0 if label == 'GREEN' else (2 if label == 'RED' else 1)


def cmd_reconfigure():
    """Re-detect current state and overwrite config."""
    log.info('Re-detecting current system state...')
    config = detect_config()
    save_config(config)
    print_config(config)
    print(f'\nConfig written to {CONFIG_PATH}')
    print('Restart the monitor service to pick up changes:')
    print('  sudo systemctl restart blinkstick-monitor')
    return 0


def cmd_monitor(config):
    """Main monitoring loop."""
    global _reload_requested

    signal.signal(signal.SIGHUP, request_reload)
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    led_count = config.get('led_count', 2)
    interval = config.get('check_interval', 10)
    boot_delay = config.get('boot_delay', 30)
    last_color = None
    consecutive_stick_failures = 0

    # On startup, show blue briefly to indicate the monitor is alive
    set_blinkstick_color(*COLOR_BLUE, led_count)
    log.info('BlinkStick monitor starting')
    print_config(config)

    # Wait for system services to come up after boot
    uptime = 0
    try:
        with open('/proc/uptime') as f:
            uptime = float(f.read().split()[0])
    except Exception:
        pass

    if uptime < boot_delay:
        wait = int(boot_delay - uptime)
        log.info(f'System just booted ({uptime:.0f}s ago) — waiting {wait}s for services')
        time.sleep(wait)

    while True:
        # Reload config on SIGHUP
        if _reload_requested:
            _reload_requested = False
            new_config = load_config()
            if new_config is not None:
                config = new_config
                led_count = config.get('led_count', 2)
                interval = config.get('check_interval', 10)
                last_color = None  # force LED update
                log.info('Config reloaded')
                print_config(config)
            else:
                log.error('Failed to reload config — keeping current')

        issues = run_all_checks(config)
        color, label = determine_color(issues)

        if color != last_color:
            r, g, b = color
            log.info(f'Setting BlinkStick to {label}')
            if set_blinkstick_color(r, g, b, led_count):
                last_color = color
                consecutive_stick_failures = 0
            else:
                consecutive_stick_failures += 1
                if consecutive_stick_failures >= 6:
                    log.error('BlinkStick unreachable for 60s+ — will keep retrying')
                    consecutive_stick_failures = 0

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description='BlinkStick Health Monitor for homelab systems',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  blinkstick-monitor                  Run the monitor loop (used by systemd)
  blinkstick-monitor --reconfigure    Re-snapshot current state as "healthy"
  blinkstick-monitor --status         Print current health check results
  blinkstick-monitor --check-once     Run one check, set LED, and exit

Config: /etc/blinkstick-monitor.conf
Reload: systemctl kill -s HUP blinkstick-monitor
        """)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--reconfigure', action='store_true',
                       help='Re-detect current state as healthy baseline and save config')
    group.add_argument('--status', action='store_true',
                       help='Print current health and exit (no LED change)')
    group.add_argument('--check-once', action='store_true',
                       help='Run one check cycle, set LED, and exit')

    args = parser.parse_args()

    if args.reconfigure:
        sys.exit(cmd_reconfigure())

    config = load_or_create_config()

    if args.status:
        sys.exit(cmd_status(config))
    elif args.check_once:
        sys.exit(cmd_check_once(config))
    else:
        try:
            cmd_monitor(config)
        except KeyboardInterrupt:
            log.info('Shutting down')
            led_count = config.get('led_count', 2)
            set_blinkstick_color(*COLOR_OFF, led_count)


if __name__ == '__main__':
    main()
