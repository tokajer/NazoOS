# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads the system state without root rights."""

import fcntl
import json
import os
import re
import struct
import time
from pathlib import Path

from nazoos_common import proc
from nazoos_common.helper import write_atomic

STATUS = Path("/var/lib/nazoos-update/status.json")
# btrfs subvolume flags: BTRFS_IOC_SUBVOL_GETFLAGS
# needs no root rights
BTRFS_IOC_SUBVOL_GETFLAGS = 0x80089419
BTRFS_SUBVOL_RDONLY = 1 << 1
# Error kinds in "error"; qml/Main.qml and notify.py compare these strings
ERROR_REFRESH = "refresh"
ERROR_CONFLICT = "conflict"
# Written by an update; later checks keep them (collect() hides
# needs_reboot after the next boot)
UPDATE_KEYS = ("needs_reboot", "updated")


def read_status():
    try:
        return json.loads(STATUS.read_text())
    except (OSError, ValueError):
        return {}


def write(data):
    """Root only: write DATA as the new status. Keeps last_ok of the last
    working check and UPDATE_KEYS that DATA does not set."""
    old = read_status()
    now = int(time.time())
    data["checked"] = now
    # Time of the last check that worked: the notifier only complains
    # about failing checks when they keep failing (laptop offline, ...)
    data["last_ok"] = now if not data.get("error") else old.get("last_ok", 0)
    for k in UPDATE_KEYS:
        if k not in data and k in old:
            data[k] = old[k]
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(STATUS, json.dumps(data, indent=1))


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
    or 0 when it runs normally. The snapshot is mounted "rw";
    only the subvolume itself is read-only."""
    opts = proc.out(["findmnt", "--noheadings", "--output", "OPTIONS",
                     "/"]).strip().split(",")
    for o in opts:
        m = re.fullmatch(r"subvol=/@/\.snapshots/(\d+)/snapshot", o)
        if m and ("ro" in opts or subvol_readonly("/")):
            return int(m.group(1))
    return 0


def collect():
    st = read_status()
    # Restarted since the update: no restart needed any more
    if st.get("needs_reboot") and st.get("updated", 0) < proc.boot_time():
        st["needs_reboot"] = False
    st["snapshot"] = booted_snapshot()
    st["live"] = proc.is_live()
    st["packages"] = st.get("packages") or []
    st["flatpaks"] = st.get("flatpaks") or []
    st["count"] = len(st["packages"]) + len(st["flatpaks"])
    return st
