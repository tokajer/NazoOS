# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drives, USB input devices and the VM check, read without root rights and
used by the probes and by the root actions (the helper applies the same
rules as the GUI).
"""

import json
import re
from pathlib import Path

from nazoos_common import proc

# Drives: file systems offered for automatic mounting, and the marker that
# identifies fstab lines written by nazoos-welcome
AUTOMOUNT_FS = ["ext4", "btrfs", "xfs", "ntfs", "exfat"]
FSTAB_MARKER = "# nazoos-welcome automount"
MOUNT_BASE = "/mnt"


def in_vm():
    return proc.rc(["systemd-detect-virt", "--vm", "--quiet"]) == 0


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
    ours = set(re.findall(re.escape(FSTAB_MARKER)
                          + r"\nUUID=(\S+)", fstab))
    result = []
    for d in devs:
        uuid = d.get("uuid")
        if (not uuid or d.get("fstype") not in AUTOMOUNT_FS
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
