# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads the system state without root rights."""

import fcntl
import json
import os
import re
import struct
import subprocess
from pathlib import Path

STATUS = Path("/var/lib/nazoos-update/status.json")
# Written by nazoos-welcome (NazoOS kernel opt-in, ADR 0008)
KERNEL_PREFER = Path("/var/lib/nazoos/kernel-prefer")
KERNEL_BOOTS = Path("/var/lib/nazoos/kernel-boots.json")
KERNEL_STABLE_BOOTS = 3
# btrfs subvolume flags (same as the helper): BTRFS_IOC_SUBVOL_GETFLAGS
# needs no root rights
BTRFS_IOC_SUBVOL_GETFLAGS = 0x80089419
BTRFS_SUBVOL_RDONLY = 1 << 1


def read_status():
    try:
        return json.loads(STATUS.read_text())
    except (OSError, ValueError):
        return {}


def subvol_readonly(path="/"):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return False
    try:
        buf = bytearray(8)
        fcntl.ioctl(fd, BTRFS_IOC_SUBVOL_GETFLAGS, buf)
        return bool(struct.unpack("=Q", buf)[0] & BTRFS_SUBVOL_RDONLY)
    except OSError:
        return False
    finally:
        os.close(fd)


def booted_snapshot():
    """Number of the read-only snapshot the system was started from,
    or 0 when it runs normally (same test as the helper). The snapshot
    is mounted "rw"; only the subvolume itself is read-only."""
    r = subprocess.run(["findmnt", "--noheadings", "--output", "OPTIONS",
                        "/"], capture_output=True, text=True)
    opts = r.stdout.strip().split(",")
    for o in opts:
        m = re.fullmatch(r"subvol=/@/\.snapshots/(\d+)/snapshot", o)
        if m and ("ro" in opts or subvol_readonly("/")):
            return int(m.group(1))
    return 0


def is_live():
    # nazoos-calamares-config exists only on the live medium
    return Path("/usr/share/calamares/settings.conf").exists()


def kernel_stable():
    """True when kernel-nazoos started cleanly 3 times in a row and the
    openSUSE kernel is still installed: time to offer stage 2."""
    if not KERNEL_PREFER.exists():
        return False
    try:
        boots = json.loads(KERNEL_BOOTS.read_text())
    except (OSError, ValueError):
        return False
    if boots.get("count", 0) < KERNEL_STABLE_BOOTS:
        return False
    q = subprocess.run(["rpm", "-q", "--quiet", "kernel-default"])
    only = subprocess.run(["rpm", "-q", "--quiet", "nazoos-kernel-only"])
    return q.returncode == 0 and only.returncode != 0


def collect():
    st = read_status()
    st["snapshot"] = booted_snapshot()
    st["live"] = is_live()
    st["packages"] = st.get("packages") or []
    st["flatpaks"] = st.get("flatpaks") or []
    st["count"] = len(st["packages"]) + len(st["flatpaks"])
    return st
