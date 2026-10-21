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

from nazoos_common import kernel, kernelstate, mok, proc

from . import catalog

AUTOSTART_NAME = "nazoos-welcome.desktop"


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


def repo_present(fragment):
    for f in Path("/etc/zypp/repos.d").glob("*.repo"):
        if fragment in proc.read(f):
            return True
    return False


def unit_state(unit, user=False):
    base = ["systemctl", "--user"] if user else ["systemctl"]
    enabled = proc.out(base + ["is-enabled", unit]).strip()
    active = proc.out(base + ["is-active", unit]).strip()
    return enabled in ("enabled", "enabled-runtime"), active == "active"


def grub_cmdline():
    m = kernel.CMDLINE_RE.search(proc.read(kernel.GRUB_DEFAULT_FILE))
    return m.group(2).split() if m else []


def flatpak_installed():
    if shutil.which("flatpak") is None:
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


def autostart_enabled():
    user_file = Path.home() / ".config" / "autostart" / AUTOSTART_NAME
    if not user_file.exists():
        return True
    return not re.search(r"^Hidden\s*=\s*true", proc.read(user_file),
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
                # "8ms" or "125us"
                m = re.fullmatch(r"(\d+)(m|u)s",
                                 proc.read(ep / "interval").strip())
                if m:
                    v = int(m.group(1)) / (1000 if m.group(2) == "u" else 1)
                    if v > 0 and (ms is None or v < ms):
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
    sb_raw = proc.out(["mokutil", "--sb-state"]).strip()
    sb = sb_raw.lower()
    secure_boot = "secureboot enabled" in sb
    # "SecureBoot enabled/disabled": UEFI, the kernel package queues its
    # key for MokManager either way (ADR 0024)
    uefi = "secureboot" in sb
    key = ""
    if uefi and kernel.KERNEL_PACKAGE in rpms:
        cert = mok.signing_cert()
        if cert:
            key = ("enrolled" if mok.enrolled(cert)
                   else "pending" if _requested_this_boot()
                   else "missing")
    boots = kernelstate.read_boots()
    return {
        "release": release,
        "running": release.endswith("-nazoos"),
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


_deck_found = False


def deck_in_repos():
    """The deck pattern is in the repos. Only a positive answer is kept:
    the search takes 15-20 s and collect() runs on every page change, but
    a failure (zypp lock held by the update timer) must be retried."""
    global _deck_found
    if _deck_found:
        return True
    _deck_found = proc.rc(
        ["zypper", "--non-interactive", "--no-refresh", "--quiet",
         "search", "--type", "pattern", "--match-exact",
         catalog.DECK_PATTERN], timeout=90) == 0
    return _deck_found


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
        "packmanRepo": repo_present("/packman/"),
        # gstreamer-plugins-bad-codecs only exists in Packman
        "codecs": "packman" in rpms.get("ffmpeg", "").lower()
                  or "gstreamer-plugins-bad-codecs" in rpms,
    }


def _gaming(rpms):
    scx_enabled, scx_active = unit_state("scx.service")
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
        "flathub": "flathub" in proc.out(["flatpak", "remotes",
                                          "--columns=name"]).split(),
    }


def _services(rpms):
    services = {}
    for s in catalog.SERVICES:
        enabled, active = unit_state(s["unit"], s["user"])
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
        "hasBtrfsAssistant": shutil.which("btrfs-assistant") is not None,
        "hasNazoosUpdate": shutil.which("nazoos-update") is not None,
        "hasLact": shutil.which("lact") is not None,
        "hasCoolerControl": shutil.which("coolercontrol") is not None,
        "hasDiscover": shutil.which("plasma-discover") is not None,
        "hasMyrlyn": shutil.which("myrlyn") is not None,
    }


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
    result = {
        "live": proc.is_live(),
        "autostart": autostart_enabled(),
        "drives": drives(),
        "kernel": kernel_state(),
        "channel": update_channel(),
        **_drivers(rpms, gpus()),
        **_gaming(rpms),
        **_apps(rpms, flatpak_installed()),
        **_services(rpms),
        **_kparams(),
        **_tools(),
    }
    try:
        result["sysinfo"] = sysinfo(result)
    except Exception as e:
        result["sysinfo"] = str(e)
    return result


def sysinfo(state=None):
    """Plain text summary for bug reports."""
    osr = {}
    for line in proc.read("/etc/os-release").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            osr[k] = v.strip('"')
    cpu = re.search(r"^model name\s*:\s*(.+)$", proc.read("/proc/cpuinfo"), re.M)
    mem = re.search(r"^MemTotal:\s*(\d+)", proc.read("/proc/meminfo"), re.M)
    sb = (state or {}).get("kernel", {}).get("sbState")
    if not sb:
        sb = proc.out(["mokutil", "--sb-state"]).strip()
    if not sb:
        # mokutil explains on stderr only: firmware without Secure Boot
        # (some VMs) or legacy BIOS
        sb = ("not supported" if shutil.which("mokutil")
              else "unknown (mokutil missing)")
    lines = [
        f"OS: {osr.get('PRETTY_NAME', 'unknown')} "
        f"({osr.get('VERSION_ID', '')})",
        f"Kernel: {platform.release()}",
        f"Cmdline: {proc.read('/proc/cmdline').strip()}",
        f"CPU: {cpu.group(1) if cpu else 'unknown'}",
        f"RAM: {int(mem.group(1)) // 1024 // 1024 + 1 if mem else '?'} GB",
        f"Session: {os.environ.get('XDG_SESSION_TYPE', '?')} / "
        f"{os.environ.get('XDG_CURRENT_DESKTOP', '?')}",
        f"Secure Boot: {sb}",
    ]
    state = state or {}
    for g in state["gpus"] if "gpus" in state else gpus():
        lines.append(f"GPU: {g['name']}")
    if state:
        lines.append(f"NVIDIA driver: {state.get('nvidiaDriver') or '-'}"
                     f" (loaded: {state.get('nvidiaLoaded')})")
        lines.append(f"Packman codecs: {state.get('codecs')}")
        lines.append(f"scx: {state.get('scxScheduler') or '-'}"
                     f" (active: {state.get('scxActive')})")
    return "\n".join(lines)
