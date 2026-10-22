# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads the system state without root rights."""

import json
import os
import platform
import re
import shlex
import subprocess
import traceback
from pathlib import Path

from nazoos_common import (grub, kernel, kernelstate, mok, proc, repos,
                           zypper)

from . import autostart, catalog, pollrate


def rpm_vendors(names):
    """Installed names out of `names`, with their vendor."""
    if not names:
        return {}
    found = {}
    for line in proc.out(["rpm", "-q", "--qf", "%{NAME}\t%{VENDOR}\n"]
                     + list(names)).splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    return found


def gpus():
    return parse_gpus(proc.out(["lspci", "-mm", "-nn"]))


def parse_gpus(lspci_text):
    """Display controllers out of the "lspci -mm -nn" text."""
    result = []
    for line in lspci_text.splitlines():
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


def parse_unit_states(text, units):
    """{unit: (enabled, active)} out of the `systemctl show --property=
    UnitFileState,ActiveState UNITS` text. One block per unit, in
    argument order (Id would differ for aliases)."""
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    blocks += [""] * (len(units) - len(blocks))
    result = {}
    for unit, block in zip(units, blocks, strict=False):
        props = dict(line.split("=", 1) for line in block.splitlines()
                     if "=" in line)
        result[unit] = (props.get("UnitFileState") in
                        ("enabled", "enabled-runtime"),
                        props.get("ActiveState") == "active")
    return result


def unit_states(units, user=False):
    """One systemctl call for all UNITS: {unit: (enabled, active)}."""
    if not units:
        return {}
    base = ["systemctl", "--user"] if user else ["systemctl"]
    return parse_unit_states(
        proc.out(base + ["show", "--property=UnitFileState,ActiveState"]
                 + list(units)), units)


def grub_cmdline():
    return grub.cmdline_options(proc.read(grub.GRUB_DEFAULT_FILE))


def flathub_configured():
    return "flathub" in proc.out(["flatpak", "remotes",
                                  "--columns=name"]).split()


def flatpak_installed():
    if not proc.has("flatpak"):
        return set()
    return set(proc.out(["flatpak", "list",
                     "--columns=application"]).split())


def in_vm():
    return proc.rc(["systemd-detect-virt", "--vm", "--quiet"]) == 0


def waydroid_software():
    """Waydroid's config selects software rendering (set in a VM)."""
    m = re.search(r"^\s*ro\.hardware\.egl\s*=\s*(\S+)",
                  proc.read(catalog.WAYDROID_CONFIG), re.M)
    return m is not None and \
        m.group(1) == catalog.WAYDROID_SOFTWARE["ro.hardware.egl"]


def drives():
    data = proc.out(["lsblk", "--json", "--list", "--bytes", "--output",
                     "PATH,UUID,FSTYPE,LABEL,SIZE,MOUNTPOINTS,TYPE,RM,"
                     "HOTPLUG,PKNAME"])
    try:
        devs = json.loads(data).get("blockdevices", []) if data else []
    except json.JSONDecodeError:
        devs = []
    return parse_drives(devs, proc.read("/etc/fstab"),
                        proc.out(["findmnt", "-no", "UUID", "/"]).strip())


def parse_drives(devs, fstab, root_uuid):
    """Extra drives from the lsblk "blockdevices" list: no system drive,
    no removable media, none the user already mounts by hand."""
    ours = set(re.findall(re.escape(catalog.FSTAB_MARKER)
                          + r"\nUUID=(\S+)", fstab))
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
            "size": human_size(d.get("size") or 0),
            "mountpoint": mps[0] if mps else "", "managed": managed,
        })
    return result


def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else \
                f"{n:.1f} {unit}"
        n /= 1000
    return ""


def _interval_ms(ep):
    """Polling interval of the sysfs endpoint EP in ms ("8ms" or "125us"),
    None if unknown or zero."""
    m = re.fullmatch(r"(\d+)(m|u)s", proc.read(ep / "interval").strip())
    if not m:
        return None
    v = int(m.group(1)) / (1000 if m.group(2) == "u" else 1)
    return v if v > 0 else None


def usb_input_devices():
    """Connected USB devices with a HID interface (controllers, mice,
    keyboards) and their current polling rate in Hz (0 = unknown)."""
    result = {}
    for dev in sorted(Path("/sys/bus/usb/devices").glob("*")):
        # Interfaces are named "1-2:1.0", root hubs "usb1"
        if ":" in dev.name or dev.name.startswith("usb"):
            continue
        vid = proc.read(dev / "idVendor").strip()
        pid = proc.read(dev / "idProduct").strip()
        if not vid or not pid:
            continue
        hid, ms = False, None
        for intf in dev.glob(f"{dev.name}:*"):
            if proc.read(intf / "bInterfaceClass").strip() != "03":
                continue
            hid = True
            for ep in intf.glob("ep_*"):
                if (proc.read(ep / "type").strip() != "Interrupt"
                        or proc.read(ep / "direction").strip() != "in"):
                    continue
                v = _interval_ms(ep)
                if v and (ms is None or v < ms):
                    ms = v
        if not hid:
            continue
        name = " ".join(x for x in (proc.read(dev / "manufacturer").strip(),
                                    proc.read(dev / "product").strip()) if x)
        vp = f"{vid}:{pid}"
        result.setdefault(vp, {"id": vp, "name": name or vp,
                               "hz": round(1000 / ms) if ms else 0,
                               "connected": True})
    return list(result.values())


def pollrate_state():
    """USB polling rate overrides (kernel-nazoos only)."""
    configured = pollrate.from_cmdline(grub_cmdline())
    devices = usb_input_devices()
    ids = {d["id"] for d in devices}
    # Devices with an override that are not plugged in: can be reset
    for vp in sorted(configured):
        if vp not in ids:
            devices.append({"id": vp, "name": vp, "hz": 0,
                            "connected": False})
    return {
        "available": Path(pollrate.SYSFS).exists(),
        "devices": devices,
        "configured": configured,
    }


def _requested_this_boot():
    """The helper queued the key after the last start (MOK_REQUESTED);
    a request from an earlier boot was already shown by MokManager."""
    try:
        requested = kernelstate.MOK_REQUESTED.stat().st_mtime
    except OSError:
        return False
    boot = proc.boot_time()
    return bool(boot) and requested > boot


def kernel_state():
    """NazoOS kernel opt-in (ADR 0008), without root rights."""
    names = ([kernel.KERNEL_PACKAGE, kernel.KERNEL_DEFAULT,
              kernel.KERNEL_ONLY_PACKAGE] + kernel.KMP_DEFAULT_ONLY)
    rpms = rpm_vendors(names)
    release = platform.release()
    # UEFI: the kernel package queues its key for MokManager with Secure
    # Boot on or off (ADR 0024)
    uefi, secure_boot, sb_raw = mok.sb_state()
    key = ""
    if uefi and kernel.KERNEL_PACKAGE in rpms:
        cert = mok.signing_cert(kernel.KERNEL_PACKAGE)
        if cert:
            key = ("enrolled" if mok.enrolled(cert)
                   else "pending" if _requested_this_boot()
                   else "missing")
    boots = kernelstate.read_boots()
    return {
        "release": release,
        "running": kernel.running_nazoos(),
        "installed": kernel.KERNEL_PACKAGE in rpms,
        "defaultInstalled": kernel.KERNEL_DEFAULT in rpms,
        "only": kernel.KERNEL_ONLY_PACKAGE in rpms,
        "preferred": kernelstate.PREFER.exists(),
        "boots": boots.get("count", 0),
        "stableBoots": kernelstate.STABLE_BOOTS,
        "blocked": any(p in rpms for p in kernel.KMP_DEFAULT_ONLY),
        "secureBoot": secure_boot,
        "uefi": uefi,
        "mok": key,
        "sbState": sb_raw,
    }


def session_state():
    """Steam gaming mode (nazoos-session): boot mode and handheld model."""
    conf = {}
    for line in proc.read(catalog.SESSION_CONF).splitlines():
        m = re.match(r'^(\w+)="?([^"]*)"?$', line.strip())
        if m:
            conf[m.group(1)] = m.group(2)
    handheld = ""
    if os.access(catalog.SESSION_DETECT, os.X_OK):
        try:
            r = subprocess.run([catalog.SESSION_DETECT], capture_output=True,
                               text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            r = None
        if r and r.returncode == 0:
            handheld = r.stdout.strip() or "handheld"
    return {
        "installed": proc.has("nazoos-session-select"),
        "steam": proc.has("steam"),
        "bootGaming": conf.get("BOOT_MODE") == "gaming",
        "user": conf.get("USER", ""),
        "handheld": handheld,
    }


def update_channel():
    """"stable", "beta" or "" (nazoos-repos missing or link unknown)."""
    try:
        target = os.readlink(catalog.CHANNEL_LINK)
    except OSError:
        return ""
    for name in catalog.CHANNEL_REPO_PATHS:
        if target == f"nazoos-{name}-repoindex.xml":
            return name
    return ""


# Only collect() writes it, and Backend.refresh() runs one collect() at a
# time (_refreshing)
_deck_found = False


def deck_in_repos():
    """The deck pattern is in the repos. Only a positive answer is kept:
    the search takes 15-20 s and collect() runs on every page change, but
    a failure (zypp lock held by the update timer) must be retried."""
    global _deck_found
    if _deck_found:
        return True
    _deck_found = proc.rc(
        zypper.ZYPPER + ["--no-refresh", "--quiet", "search", "--type",
                         "pattern", "--match-exact", catalog.DECK_PATTERN],
        timeout=90) == 0
    return _deck_found


def packman_repo():
    """"on" (an enabled Packman repo), "off" (only disabled ones), ""."""
    found = [on for _a, url, on in repos.repos() if "/packman/" in url]
    return "on" if any(found) else "off" if found else ""


def _drivers(rpms, gpu_list):
    vendors = {g["vendor"] for g in gpu_list}
    nvidia_variant = ""
    for variant, pkgs in catalog.NVIDIA_DRIVERS.items():
        if pkgs[1] in rpms:
            nvidia_variant = variant
    return {
        "gpus": gpu_list,
        "hasAmd": "amd" in vendors,
        "hasNvidia": "nvidia" in vendors,
        # CPU can sync its TSC itself; without it tsc=directsync helps
        "tscAdjust": re.search(r"^flags\s*:.*\btsc_adjust\b",
                               proc.read("/proc/cpuinfo"), re.M) is not None,
        "nvidiaDriver": nvidia_variant,
        "nvidiaLoaded": Path("/sys/module/nvidia").exists(),
        "rocm": catalog.ROCM_PACKAGES[0] in rpms,
        "packmanRepo": packman_repo(),
        # gstreamer-plugins-bad-codecs only exists in Packman
        "codecs": "packman" in rpms.get("ffmpeg", "").lower()
                  or "gstreamer-plugins-bad-codecs" in rpms,
    }


def _gaming(rpms, units):
    scx_enabled, scx_active = units["scx.service"]
    m = re.search(r"^\s*SCX_SCHEDULER\s*=\s*\"?([\w-]+)",
                  proc.read("/etc/default/scx"), re.M)
    deck_installed = catalog.DECK_PATTERN in rpms
    return {
        "scxInstalled": "scx" in rpms,
        "scxEnabled": scx_enabled,
        "scxActive": scx_active,
        "scxScheduler": m.group(1) if m else "",
        "pollrate": pollrate_state(),
        # Waydroid card: software rendering is used (installed) or will be
        "vm": in_vm(),
        "waydroidSoftware": waydroid_software(),
        "deckInstalled": deck_installed,
        "deckAvailable": deck_installed or deck_in_repos(),
        "session": session_state(),
    }


def _apps(rpms, flatpaks):
    apps = {}
    for a in catalog.APPS:
        if a["kind"] == "flatpak":
            apps[a["id"]] = a["refs"][0] in flatpaks
        else:
            apps[a["id"]] = all(r in rpms for r in a["refs"])
    return {
        "apps": apps,
        "flathub": flathub_configured(),
    }


def _services(rpms, system_units, user_units):
    services = {}
    for s in catalog.SERVICES:
        enabled, active = (user_units if s["user"]
                           else system_units)[s["unit"]]
        services[s["id"]] = {"installed": s["package"] in rpms,
                             "enabled": enabled, "active": active}
    return {"services": services}


def _kparams():
    configured = grub_cmdline()
    active_cmdline = proc.read("/proc/cmdline").split()
    kparams = {}
    for k in catalog.KERNEL_PARAMS:
        kparams[k["id"]] = {"configured": k["param"] in configured,
                            "active": k["param"] in active_cmdline}
    return {"kparams": kparams}


def _tools():
    return {
        "hasBtrfsAssistant": proc.has("btrfs-assistant"),
        "hasNazoosUpdate": proc.has("nazoos-update"),
        "hasLact": proc.has("lact"),
        "hasCoolerControl": proc.has("coolercontrol"),
        "hasDiscover": proc.has("plasma-discover"),
        "hasMyrlyn": proc.has("myrlyn"),
    }


def _part(default, probe):
    """probe() or, if it fails, DEFAULT: one broken probe does not drop
    the rest of the state."""
    try:
        return probe()
    except Exception:
        traceback.print_exc()
        return default


def collect():
    """Full state for the UI, as plain JSON-friendly data."""
    rpm_names = (["scx", catalog.DECK_PATTERN, "ffmpeg",
                  "gstreamer-plugins-bad-codecs"]
                 + [p for v in catalog.NVIDIA_DRIVERS.values() for p in v]
                 + catalog.ROCM_PACKAGES
                 + [s["package"] for s in catalog.SERVICES]
                 + [r for a in catalog.APPS if a["kind"] == "rpm"
                    for r in a["refs"]])
    rpms = rpm_vendors(sorted(set(rpm_names)))
    system_units = unit_states(["scx.service"] + [
        s["unit"] for s in catalog.SERVICES if not s["user"]])
    user_units = unit_states(
        [s["unit"] for s in catalog.SERVICES if s["user"]], user=True)
    result = {
        "live": proc.is_live(),
        "autostart": autostart.enabled(),
        "drives": _part([], drives),
        "kernel": _part({}, kernel_state),
        "channel": _part("", update_channel),
        **_part({}, lambda: _drivers(rpms, gpus())),
        **_part({}, lambda: _gaming(rpms, system_units)),
        **_part({}, lambda: _apps(rpms, flatpak_installed())),
        **_part({}, lambda: _services(rpms, system_units, user_units)),
        **_part({}, _kparams),
        **_part({}, _tools),
    }
    return result

