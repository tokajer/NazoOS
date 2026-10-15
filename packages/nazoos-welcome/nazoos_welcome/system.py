# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads the system state without root rights."""

import json
import os
import platform
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from . import catalog, kernel

AUTOSTART_NAME = "nazoos-welcome.desktop"


def _out(cmd, timeout=30):
    if shutil.which(cmd[0]) is None:
        return ""
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _rc(cmd, timeout=30):
    if shutil.which(cmd[0]) is None:
        return 127
    try:
        return subprocess.run(cmd, capture_output=True,
                              timeout=timeout).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 1


def _read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def rpm_installed(names):
    """Installed names out of `names`, with their vendor."""
    if not names:
        return {}
    found = {}
    for line in _out(["rpm", "-q", "--qf", "%{NAME}\t%{VENDOR}\n"]
                     + list(names)).splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    return found


def gpus():
    result = []
    for line in _out(["lspci", "-mm", "-nn"]).splitlines():
        try:
            f = shlex.split(line)
        except ValueError:
            continue
        if len(f) < 4 or not re.search(r"\[03(00|02|80)\]", f[1]):
            continue
        vendor_id = re.search(r"\[([0-9a-f]{4})\]$", f[2])
        vid = vendor_id.group(1) if vendor_id else ""
        vendor = {"1002": "amd", "10de": "nvidia",
                  "8086": "intel"}.get(vid, "other")
        name = re.sub(r"\s*\[[0-9a-f]{4}\]$", "", f[3])
        vname = re.sub(r"\s*\[[0-9a-f]{4}\]$", "", f[2])
        result.append({"vendor": vendor, "name": f"{vname} {name}"})
    return result


def repo_present(fragment):
    for f in Path("/etc/zypp/repos.d").glob("*.repo"):
        if fragment in _read(f):
            return True
    return False


def unit_state(unit, user=False):
    base = ["systemctl", "--user"] if user else ["systemctl"]
    enabled = _out(base + ["is-enabled", unit]).strip()
    active = _out(base + ["is-active", unit]).strip()
    return enabled in ("enabled", "enabled-runtime"), active == "active"


def grub_cmdline():
    m = re.search(r'^GRUB_CMDLINE_LINUX_DEFAULT=(["\']?)(.*?)\1\s*$',
                  _read("/etc/default/grub"), re.M)
    return m.group(2).split() if m else []


def flatpak_installed():
    if shutil.which("flatpak") is None:
        return set()
    return set(_out(["flatpak", "list",
                     "--columns=application"]).split())


def is_live():
    # nazoos-calamares-config exists only on the live medium
    return Path("/usr/share/calamares/settings.conf").exists()


def in_vm():
    return _rc(["systemd-detect-virt", "--vm", "--quiet"]) == 0


def waydroid_software():
    """Waydroid's config selects software rendering (set in a VM)."""
    m = re.search(r"^\s*ro\.hardware\.egl\s*=\s*(\S+)",
                  _read(catalog.WAYDROID_CONFIG), re.M)
    return m is not None and \
        m.group(1) == catalog.WAYDROID_SOFTWARE["ro.hardware.egl"]


def autostart_enabled():
    user_file = Path.home() / ".config" / "autostart" / AUTOSTART_NAME
    if not user_file.exists():
        return True
    return not re.search(r"^Hidden\s*=\s*true", _read(user_file),
                         re.M | re.I)


def set_autostart(enabled):
    user_file = Path.home() / ".config" / "autostart" / AUTOSTART_NAME
    if enabled:
        user_file.unlink(missing_ok=True)
    else:
        user_file.parent.mkdir(parents=True, exist_ok=True)
        # Hidden=true overrides the system-wide autostart entry
        user_file.write_text("[Desktop Entry]\nType=Application\n"
                             "Name=NazoOS Welcome\nHidden=true\n")


def drives():
    data = _out(["lsblk", "--json", "--list", "--bytes", "--output",
                 "PATH,UUID,FSTYPE,LABEL,SIZE,MOUNTPOINTS,TYPE,RM,"
                 "HOTPLUG,PKNAME"])
    try:
        devs = json.loads(data).get("blockdevices", []) if data else []
    except json.JSONDecodeError:
        devs = []
    fstab = _read("/etc/fstab")
    ours = set(re.findall(re.escape(catalog.FSTAB_MARKER)
                          + r"\nUUID=(\S+)", fstab))
    root_uuid = _out(["findmnt", "-no", "UUID", "/"]).strip()
    result = []
    for d in devs:
        uuid = d.get("uuid")
        if (not uuid or d.get("fstype") not in catalog.AUTOMOUNT_FS
                or d.get("rm") or d.get("hotplug") or uuid == root_uuid):
            continue
        mps = [m for m in (d.get("mountpoints") or []) if m]
        managed = uuid in ours
        if not managed and (uuid in fstab or any(
                not m.startswith("/run/media/") for m in mps)):
            continue
        result.append({
            "uuid": uuid, "path": d.get("path", ""),
            "fstype": d.get("fstype"), "label": d.get("label") or "",
            "size": _human(d.get("size") or 0),
            "mountpoint": mps[0] if mps else "", "managed": managed,
        })
    return result


def _human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else \
                f"{n:.1f} {unit}"
        n /= 1000
    return ""


def usb_input_devices():
    """Connected USB devices with a HID interface (controllers, mice,
    keyboards) and their current polling rate in Hz (0 = unknown)."""
    result = {}
    for dev in sorted(Path("/sys/bus/usb/devices").glob("*")):
        # Interfaces are named "1-2:1.0", root hubs "usb1"
        if ":" in dev.name or dev.name.startswith("usb"):
            continue
        vid = _read(dev / "idVendor").strip()
        pid = _read(dev / "idProduct").strip()
        if not vid or not pid:
            continue
        hid, ms = False, None
        for intf in dev.glob(f"{dev.name}:*"):
            if _read(intf / "bInterfaceClass").strip() != "03":
                continue
            hid = True
            for ep in intf.glob("ep_*"):
                if (_read(ep / "type").strip() != "Interrupt"
                        or _read(ep / "direction").strip() != "in"):
                    continue
                # "8ms" or "125us"
                m = re.fullmatch(r"(\d+)(m|u)s",
                                 _read(ep / "interval").strip())
                if m:
                    v = int(m.group(1)) / (1000 if m.group(2) == "u" else 1)
                    if v > 0 and (ms is None or v < ms):
                        ms = v
        if not hid:
            continue
        name = " ".join(x for x in (_read(dev / "manufacturer").strip(),
                                    _read(dev / "product").strip()) if x)
        vp = f"{vid}:{pid}"
        result.setdefault(vp, {"id": vp, "name": name or vp,
                               "hz": round(1000 / ms) if ms else 0,
                               "connected": True})
    return list(result.values())


def pollrate_state():
    """USB polling rate overrides (kernel-nazoos only)."""
    configured = {}
    for opt in grub_cmdline():
        if opt.startswith(catalog.POLLRATE_PARAM + "="):
            configured = catalog.pollrate_parse(opt.split("=", 1)[1])
    devices = usb_input_devices()
    ids = {d["id"] for d in devices}
    # Devices with an override that are not plugged in: can be reset
    for vp in sorted(configured):
        if vp not in ids:
            devices.append({"id": vp, "name": vp, "hz": 0,
                            "connected": False})
    return {
        "available": Path(catalog.POLLRATE_SYSFS).exists(),
        "devices": devices,
        "configured": configured,
    }


def kernel_state():
    """NazoOS kernel opt-in (ADR 0008), without root rights."""
    names = ([catalog.KERNEL_PACKAGE, catalog.KERNEL_DEFAULT,
              catalog.KERNEL_ONLY_PACKAGE] + catalog.KMP_DEFAULT_ONLY)
    rpms = rpm_installed(names)
    release = platform.release()
    sb = _out(["mokutil", "--sb-state"]).lower()
    secure_boot = "secureboot enabled" in sb
    mok = ""
    if secure_boot and catalog.KERNEL_PACKAGE in rpms:
        certs = [f for f in _out(["rpm", "-ql", catalog.KERNEL_PACKAGE]).split()
                 if re.fullmatch(r"/etc/uefi/certs/\w+\.crt", f)]
        if certs:
            test = _out(["mokutil", "--test-key", certs[0]]).lower()
            mok = ("enrolled" if "already enrolled" in test
                   else "pending" if certs[0].rsplit("/", 1)[1][:-4].lower()
                   in _out(["mokutil", "--list-new"]).lower().replace(":", "")
                   else "missing")
    boots = kernel.read_boots()
    return {
        "release": release,
        "running": release.endswith("-nazoos"),
        "installed": catalog.KERNEL_PACKAGE in rpms,
        "defaultInstalled": catalog.KERNEL_DEFAULT in rpms,
        "only": catalog.KERNEL_ONLY_PACKAGE in rpms,
        "preferred": kernel.PREFER.exists(),
        "boots": boots.get("count", 0),
        "stableBoots": catalog.KERNEL_STABLE_BOOTS,
        "blocked": any(p in rpms for p in catalog.KMP_DEFAULT_ONLY),
        "secureBoot": secure_boot,
        "mok": mok,
    }


def session_state():
    """Steam gaming mode (nazoos-session): boot mode and handheld model."""
    conf = {}
    for line in _read(catalog.SESSION_CONF).splitlines():
        m = re.match(r'^(\w+)="?([^"]*)"?$', line.strip())
        if m:
            conf[m.group(1)] = m.group(2)
    handheld = ""
    if os.access(catalog.SESSION_DETECT, os.X_OK):
        r = subprocess.run([catalog.SESSION_DETECT], capture_output=True,
                           text=True)
        if r.returncode == 0:
            handheld = r.stdout.strip() or "handheld"
    return {
        "installed": shutil.which("nazoos-session-select") is not None,
        "steam": shutil.which("steam") is not None,
        "bootGaming": conf.get("BOOT_MODE") == "gaming",
        "user": conf.get("USER", ""),
        "handheld": handheld,
    }


def collect():
    """Full state for the UI, as plain JSON-friendly data."""
    gpu_list = gpus()
    vendors = {g["vendor"] for g in gpu_list}

    rpm_names = (["scx", catalog.DECK_PATTERN, "ffmpeg",
                  "gstreamer-plugins-bad-codecs",
                  "nazoos-update", "btrfs-assistant", "plasma-discover",
                  "discover6", "myrlyn", "lact", "coolercontrol"]
                 + [p for v in catalog.NVIDIA_DRIVERS.values() for p in v]
                 + catalog.ROCM_PACKAGES
                 + [s["package"] for s in catalog.SERVICES]
                 + [r for a in catalog.APPS if a["kind"] == "rpm"
                    for r in a["refs"]])
    rpms = rpm_installed(sorted(set(rpm_names)))
    flatpaks = flatpak_installed()

    apps = {}
    for a in catalog.APPS:
        if a["kind"] == "flatpak":
            apps[a["id"]] = a["refs"][0] in flatpaks
        else:
            apps[a["id"]] = all(r in rpms for r in a["refs"])

    services = {}
    for s in catalog.SERVICES:
        enabled, active = unit_state(s["unit"], s["user"])
        services[s["id"]] = {"installed": s["package"] in rpms,
                             "enabled": enabled, "active": active}

    configured = grub_cmdline()
    active_cmdline = _read("/proc/cmdline").split()
    kparams = {}
    for k in catalog.KERNEL_PARAMS:
        kparams[k["id"]] = {"configured": k["param"] in configured,
                            "active": k["param"] in active_cmdline}

    scx_enabled, scx_active = unit_state("scx.service")
    m = re.search(r"^\s*SCX_SCHEDULER\s*=\s*\"?([\w-]+)",
                  _read("/etc/default/scx"), re.M)

    nvidia_variant = ""
    for variant, pkgs in catalog.NVIDIA_DRIVERS.items():
        if pkgs[1] in rpms:
            nvidia_variant = variant

    deck_installed = _rc(["rpm", "-q", "--whatprovides",
                          f"pattern() = {catalog.DECK_PATTERN}"]) == 0
    deck_available = deck_installed or _rc(
        ["zypper", "--non-interactive", "--no-refresh", "--quiet",
         "search", "--type", "pattern", "--match-exact",
         catalog.DECK_PATTERN]) == 0

    return {
        "live": is_live(),
        "autostart": autostart_enabled(),
        "gpus": gpu_list,
        "hasAmd": "amd" in vendors,
        "hasNvidia": "nvidia" in vendors,
        # CPU can sync its TSC itself; without it tsc=directsync helps
        "tscAdjust": re.search(r"^flags\s*:.*\btsc_adjust\b",
                               _read("/proc/cpuinfo"), re.M) is not None,
        "nvidiaDriver": nvidia_variant,
        "nvidiaLoaded": Path("/sys/module/nvidia").exists(),
        "rocm": catalog.ROCM_PACKAGES[0] in rpms,
        "packmanRepo": repo_present("/packman/"),
        # gstreamer-plugins-bad-codecs only exists in Packman
        "codecs": "packman" in rpms.get("ffmpeg", "").lower()
                  or "gstreamer-plugins-bad-codecs" in rpms,
        "scxInstalled": "scx" in rpms,
        "scxEnabled": scx_enabled,
        "scxActive": scx_active,
        "scxScheduler": m.group(1) if m else "",
        "kparams": kparams,
        "pollrate": pollrate_state(),
        "services": services,
        "apps": apps,
        # Waydroid card: software rendering is used (installed) or will be
        "vm": in_vm(),
        "waydroidSoftware": waydroid_software(),
        "flathub": "flathub" in _out(["flatpak", "remotes",
                                      "--columns=name"]).split(),
        "deckInstalled": deck_installed,
        "deckAvailable": deck_available,
        "session": session_state(),
        "drives": drives(),
        "kernel": kernel_state(),
        "hasBtrfsAssistant": shutil.which("btrfs-assistant") is not None,
        "hasNazoosUpdate": shutil.which("nazoos-update") is not None,
        "hasLact": shutil.which("lact") is not None,
        "hasCoolerControl": shutil.which("coolercontrol") is not None,
        "hasDiscover": shutil.which("plasma-discover") is not None,
        "hasMyrlyn": shutil.which("myrlyn") is not None,
    }


def sysinfo(state=None):
    """Plain text summary for bug reports."""
    osr = {}
    for line in _read("/etc/os-release").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            osr[k] = v.strip('"')
    cpu = re.search(r"^model name\s*:\s*(.+)$", _read("/proc/cpuinfo"), re.M)
    mem = re.search(r"^MemTotal:\s*(\d+)", _read("/proc/meminfo"), re.M)
    sb = _out(["mokutil", "--sb-state"]).strip() or "unknown"
    lines = [
        f"OS: {osr.get('PRETTY_NAME', 'unknown')} "
        f"({osr.get('VERSION_ID', '')})",
        f"Kernel: {platform.release()}",
        f"Cmdline: {_read('/proc/cmdline').strip()}",
        f"CPU: {cpu.group(1) if cpu else 'unknown'}",
        f"RAM: {int(mem.group(1)) // 1024 // 1024 + 1 if mem else '?'} GB",
        f"Session: {os.environ.get('XDG_SESSION_TYPE', '?')} / "
        f"{os.environ.get('XDG_CURRENT_DESKTOP', '?')}",
        f"Secure Boot: {sb}",
    ]
    state = state or {}
    for g in state.get("gpus", gpus()):
        lines.append(f"GPU: {g['name']}")
    if state:
        lines.append(f"NVIDIA driver: {state.get('nvidiaDriver') or '-'}"
                     f" (loaded: {state.get('nvidiaLoaded')})")
        lines.append(f"Packman codecs: {state.get('codecs')}")
        lines.append(f"scx: {state.get('scxScheduler') or '-'}"
                     f" (active: {state.get('scxActive')})")
    return "\n".join(lines)
