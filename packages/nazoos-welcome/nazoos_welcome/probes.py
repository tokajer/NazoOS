# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads the system state without root rights."""

import os
import platform
import re
import subprocess
import traceback
from pathlib import Path

from nazoos_common import (grub, kernel, kernelstate, mok, proc, shellconf,
                           zypper)

from . import appicons, autostart, catalog, hw, pollrate, query, system


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
    return parse_unit_states(
        proc.out(proc.systemctl(user) + ["show", "--property=UnitFileState,ActiveState"]
                 + list(units)), units)


def grub_cmdline():
    return grub.cmdline_options(proc.read(grub.GRUB_DEFAULT_FILE))


def flatpak_installed():
    if not proc.has("flatpak"):
        return set()
    return set(proc.out(["flatpak", "list",
                     "--columns=application"]).split())


def waydroid_software():
    """Waydroid's config selects software rendering (set in a VM)."""
    m = re.search(r"^\s*ro\.hardware\.egl\s*=\s*(\S+)",
                  proc.read(system.WAYDROID_CONFIG), re.M)
    return m is not None and \
        m.group(1) == system.WAYDROID_SOFTWARE["ro.hardware.egl"]


def pollrate_state():
    """USB polling rate overrides (kernel-nazoos only)."""
    configured = pollrate.from_cmdline(grub_cmdline())
    devices = hw.usb_input_devices()
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
    rpms = query.rpm_vendors(names)
    release = platform.release()
    # UEFI: the kernel package queues its key for MokManager with Secure
    # Boot on or off (ADR 0024)
    uefi, secure_boot, sb_raw = mok.sb_state()
    key = ""
    if uefi and kernel.KERNEL_PACKAGE in rpms:
        cert = mok.signing_cert(kernel.KERNEL_PACKAGE)
        if cert:
            key = (mok.ENROLLED if mok.enrolled(cert)
                   else mok.PENDING if _requested_this_boot()
                   else mok.MISSING)
    boots = kernelstate.read_boots().get("count", 0)
    running = kernel.running_nazoos()
    preferred = kernelstate.PREFER.exists()
    default_installed = kernel.KERNEL_DEFAULT in rpms
    only = kernel.KERNEL_ONLY_PACKAGE in rpms
    state = {
        "release": release,
        "running": running,
        "installed": kernel.KERNEL_PACKAGE in rpms,
        "defaultInstalled": default_installed,
        "only": only,
        "preferred": preferred,
        "boots": boots,
        "stableBoots": kernelstate.STABLE_BOOTS,
        "stage2": (kernel.stage2_state(preferred, boots, default_installed,
                                       only) if running else ""),
        "blocked": any(p in rpms for p in kernel.KMP_DEFAULT_ONLY),
        "secureBoot": secure_boot,
        "uefi": uefi,
        "mok": key,
        "sbState": sb_raw,
    }
    state["phase"] = kernel_phase(state)
    return state


def kernel_phase(k):
    """What the kernel card says, from the kernel_state() dict K."""
    if k["blocked"]:
        return "blocked"
    if k["running"]:
        return "running"
    if not k["installed"]:
        return ""
    if k["secureBoot"] and k["mok"] == mok.MISSING:
        return "key-missing"
    if k["secureBoot"] and k["mok"] == mok.PENDING:
        return "key-pending"
    return "installed" if k["preferred"] else "not-preferred"


def session_state():
    """Steam gaming mode (nazoos-session): boot mode and handheld model."""
    # The tool owns the file format: ask it, do not parse its file
    text = proc.out([system.SESSION_CTL, "status"], timeout=10)
    handheld = ""
    if os.access(system.SESSION_DETECT, os.X_OK):
        try:
            r = subprocess.run([system.SESSION_DETECT], capture_output=True,
                               text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            r = None
        if r and r.returncode == 0:
            handheld = r.stdout.strip() or "handheld"
    return {
        "installed": proc.has("nazoos-session-select"),
        "steam": proc.has("steam"),
        "bootGaming": shellconf.get_var(text, "BOOT_MODE") == "gaming",
        "user": shellconf.get_var(text, "USER"),
        "handheld": handheld,
    }


def update_channel():
    """"stable", "beta" or "" (nazoos-repos missing or link unknown)."""
    try:
        target = os.readlink(system.CHANNEL_LINK)
    except OSError:
        return ""
    for name in system.CHANNEL_REPO_PATHS:
        if target == f"nazoos-{name}-repoindex.xml":
            return name
    return ""


# Seconds the pattern search may take (15-20 s normally, slower when the
# repos are cold)
DECK_SEARCH_TIMEOUT = 90

# Only collect() writes it, and Backend's CoalescedLoad runs one collect()
# at a time
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
                         "pattern", "--match-exact", system.DECK_PATTERN],
        timeout=DECK_SEARCH_TIMEOUT) == 0
    return _deck_found


# Each part names the RPMs it looks up; collect() asks rpm once for all
_DRIVERS_RPMS = (["ffmpeg", "gstreamer-plugins-bad-codecs"]
                 + [p for v in catalog.NVIDIA_DRIVERS.values() for p in v]
                 + system.ROCM_PACKAGES)


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
        "rocm": system.ROCM_PACKAGES[0] in rpms,
        "packmanRepo": query.packman_repo(),
        # gstreamer-plugins-bad-codecs only exists in Packman
        "codecs": "packman" in rpms.get("ffmpeg", "").lower()
                  or "gstreamer-plugins-bad-codecs" in rpms,
    }


_GAMING_RPMS = ["scx", system.DECK_PATTERN]


def _gaming(rpms, units):
    scx_enabled, scx_active = units["scx.service"]
    scheduler = shellconf.get_var(proc.read("/etc/default/scx"),
                                  "SCX_SCHEDULER")
    deck_installed = system.DECK_PATTERN in rpms
    return {
        "scxInstalled": "scx" in rpms,
        "scxEnabled": scx_enabled,
        "scxActive": scx_active,
        "scxScheduler": scheduler,
        "pollrate": pollrate_state(),
        # Waydroid card: software rendering is used (installed) or will be
        "vm": hw.in_vm(),
        "waydroidSoftware": waydroid_software(),
        "deckInstalled": deck_installed,
        "deckAvailable": deck_installed or deck_in_repos(),
        "session": session_state(),
    }


_APPS_RPMS = [r for a in catalog.APPS if a["kind"] == "rpm" for r in a["refs"]]


def _apps(rpms, flatpaks):
    apps = {}
    for a in catalog.APPS:
        if a["kind"] == "flatpak":
            apps[a["id"]] = a["refs"][0] in flatpaks
        else:
            apps[a["id"]] = all(r in rpms for r in a["refs"])
    return {
        "apps": apps,
        "flathub": query.flathub_configured(),
    }


_SERVICES_RPMS = [s["package"] for s in catalog.SERVICES]


def _services(rpms, system_units, user_units):
    services = {}
    for s in catalog.SERVICES:
        enabled, active = (user_units if s["user"]
                           else system_units)[s["unit"]]
        services[s["id"]] = {"installed": s["package"] in rpms,
                             "enabled": enabled, "active": active}
    return {"services": services}


def kparam_shown(k, drivers):
    """Kernel option K (catalog.KERNEL_PARAMS) is offered on this hardware.
    DRIVERS: the _drivers() part of the state."""
    return ((k.get("gpu") != "amd" or drivers.get("hasAmd") is True)
            and (k.get("cpu") != "no-tsc-adjust"
                 or drivers.get("tscAdjust") is False))


def _kparams(drivers):
    configured = grub_cmdline()
    active_cmdline = proc.read("/proc/cmdline").split()
    kparams = {}
    for k in catalog.KERNEL_PARAMS:
        kparams[k["id"]] = {"configured": k["param"] in configured,
                            "active": k["param"] in active_cmdline,
                            "shown": kparam_shown(k, drivers)}
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
    rpms = query.rpm_vendors(sorted(set(
        _DRIVERS_RPMS + _GAMING_RPMS + _APPS_RPMS + _SERVICES_RPMS)))
    system_units = unit_states(["scx.service"] + [
        s["unit"] for s in catalog.SERVICES if not s["user"]])
    user_units = unit_states(
        [s["unit"] for s in catalog.SERVICES if s["user"]], user=True)
    drivers = _part({}, lambda: _drivers(rpms, query.gpus()))
    result = {
        "live": proc.is_live(),
        "autostart": autostart.enabled(),
        "drives": _part([], hw.drives),
        "kernel": _part({}, kernel_state),
        "channel": _part("", update_channel),
        "appIcons": _part({}, lambda: appicons.collect(catalog.APPS)),
        **drivers,
        **_part({}, lambda: _gaming(rpms, system_units)),
        **_part({}, lambda: _apps(rpms, flatpak_installed())),
        **_part({}, lambda: _services(rpms, system_units, user_units)),
        **_part({}, lambda: _kparams(drivers)),
        **_part({}, _tools),
    }
    return result

