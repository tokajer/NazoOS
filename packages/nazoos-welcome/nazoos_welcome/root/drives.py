# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Extra drives mounted at boot (fstab lines with hw.FSTAB_MARKER)."""

import os
import re
from pathlib import Path

from nazoos_common import helper
from nazoos_common.helper import Fail, arg, say, write_atomic

from .. import hw
from .base import caller

FSTAB = Path("/etc/fstab")
# suse-module-tools blacklists ntfs3; an /etc file of the same name wins
NTFS3_BLACKLIST = "60-blacklist_fs-ntfs3.conf"


def sanitize(name):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return name[:40]


def unblacklist_ntfs3():
    """suse-module-tools blacklists the ntfs3 driver ("not supported by
    SUSE"). The blacklist also blocks the alias fs-ntfs3 the kernel asks
    for when mounting, so an fstab entry fails with "unknown filesystem
    type". Its own way out, "modprobe ntfs3" in a terminal, links the
    same file name in /etc/modprobe.d to /dev/null (unblacklist script);
    without a terminal it does nothing. Do the same here, only when the
    user adds an NTFS drive. Dolphin is not affected: udisks falls back
    to ntfs-3g (FUSE)."""
    vendor = Path("/usr/lib/modprobe.d", NTFS3_BLACKLIST)
    local = Path("/etc/modprobe.d", NTFS3_BLACKLIST)
    if not vendor.exists() or local.is_symlink() or local.exists():
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    local.symlink_to("/dev/null")
    say(f"ntfs3 driver allowed: {local} -> /dev/null")


def mount_options(fstype, uid, gid):
    """(file system type, mount options) for the fstab line."""
    opts = "nofail,x-systemd.device-timeout=10s,noatime"
    if fstype == "ntfs":
        fstype = "ntfs3"
        opts += f",uid={uid},gid={gid},umask=022,windows_names"
        unblacklist_ntfs3()
    elif fstype == "exfat":
        opts += f",uid={uid},gid={gid},umask=022"
    elif fstype == "btrfs":
        opts += ",compress=zstd:1"
    return fstype, opts


def without_entry(text, uuid):
    """(fstab text without our entry for UUID, its mount point or None)."""
    lines = text.splitlines()
    out, mnt, i = [], None, 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line == hw.FSTAB_MARKER and nxt.startswith(f"UUID={uuid} "):
            mnt = nxt.split()[1]
            i += 2
            continue
        out.append(line)
        i += 1
    return "\n".join(out) + "\n", mnt


def _undo_add(uuid, mnt, created):
    write_atomic(FSTAB, without_entry(FSTAB.read_text(), uuid)[0])
    helper.run(["systemctl", "daemon-reload"], check=False)
    if created:
        try:
            mnt.rmdir()
        except OSError:
            pass


def automount_add(args):
    uuid = arg(args, 0)
    # The GUI only offers non-removable extra drives; the helper is the
    # trust boundary and applies the same rule (hw.drives)
    dev = next((d for d in hw.drives()
                if d["uuid"] == uuid and not d["managed"]), None)
    if dev is None:
        raise Fail("this drive cannot be added here "
                   "(removable or system drive)")
    fstype = dev["fstype"]
    base = sanitize(dev["label"]) or uuid[:8]
    mnt = Path(hw.MOUNT_BASE, base)
    n = 2
    while mnt.exists() and any(mnt.iterdir()):
        mnt = Path(hw.MOUNT_BASE, f"{base}-{n}")
        n += 1
    uid = caller()[0]
    gid = int(helper.output(["id", "-g", str(uid)]).strip() or 100)
    fstype, opts = mount_options(fstype, uid, gid)
    created = not mnt.exists()
    mnt.mkdir(parents=True, exist_ok=True)
    line = f"UUID={uuid} {mnt} {fstype} {opts} 0 0"
    text = FSTAB.read_text()
    if not text.endswith("\n"):
        text += "\n"
    write_atomic(FSTAB, text + f"{hw.FSTAB_MARKER}\n{line}\n")
    say(line)
    # A failed mount must not leave a boot-time entry (or a stray directory)
    # behind, whether mount returns non-zero or something raises
    try:
        helper.run(["systemctl", "daemon-reload"])
        rc = helper.run(["mount", str(mnt)], check=False)
    except Exception:
        _undo_add(uuid, mnt, created)
        raise
    if rc != 0:
        _undo_add(uuid, mnt, created)
        raise Fail("the drive could not be mounted (exit code {rc})", rc=rc)
    # A fresh Linux file system belongs to root: give it to the user so
    # Steam can put a library there. Existing data is left alone.
    if fstype in ("ext4", "btrfs", "xfs"):
        st = mnt.stat()
        content = [p.name for p in mnt.iterdir()]
        if st.st_uid == 0 and set(content) <= {"lost+found"}:
            os.chown(mnt, uid, gid)
            say(f"{mnt} now belongs to uid {uid}")


def automount_remove(args):
    uuid = arg(args, 0)
    text, mnt = without_entry(FSTAB.read_text(), uuid)
    if mnt is None:
        raise Fail("only drives added by NazoOS Welcome can be removed here")
    helper.run(["umount", mnt], check=False)
    write_atomic(FSTAB, text)
    helper.run(["systemctl", "daemon-reload"])
    try:
        Path(mnt).rmdir()
    except OSError:
        pass
