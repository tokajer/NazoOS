# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot names in the boot menu, and the rollback to a snapshot."""

import gettext
import json
import time
from datetime import datetime
from pathlib import Path

from nazoos_common import proc
from nazoos_common.files import locked
from nazoos_common.helper import Fail, capture, reboot, run, say

from .. import status

# Held while snapshots are listed and named: the path unit's run and the
# one in update() must not overlap (VM 2026-10-21: the path unit listed
# before update() named its pair and then wrote "After software change")
LABEL_LOCK = "/run/nazoos-update-label.lock"


# grub2-snapper-plugin shows the userdata "bootloader" instead of
# "kernel,date,pre,zypp(zypper)". It rebuilds the menu on modify-snapshot.

def snapshots():
    r = capture(["snapper", "--jsonout", "list", "--disable-used-space"])
    try:
        return json.loads(r.stdout).get("root", [])
    except ValueError:
        return []


def last_snapshot():
    return max((s["number"] for s in snapshots()), default=0)


def system_translation():
    """Labels in the language of the system (/etc/locale.conf), not of
    the helper process (LC_ALL=C for zypper)."""
    lang = ""
    try:
        for line in Path("/etc/locale.conf").read_text().splitlines():
            if line.startswith("LANG="):
                lang = line[5:].strip().strip('"').split(".")[0]
    except OSError:
        pass
    return gettext.translation("nazoos-update", languages=[lang] if lang
                               else None, fallback=True)


def snapshot_label(s, zypp_pre, is_update, _):
    """Menu text for snapshot S, None if it gets no label. _ is gettext."""
    num = s["number"]
    if s["type"] == "pre" and num in zypp_pre:
        return _("Before update") if is_update \
            else _("Before software change")
    elif s["type"] == "post" and s.get("pre-number") in zypp_pre:
        return _("After update") if is_update \
            else _("After software change")
    elif s["type"] == "single":
        d = s.get("description") or ""
        if d == "timeline":
            return _("Automatic snapshot")
        if d.startswith("nazoos-update: rollback"):
            # snapper keeps a read-only backup of the state before the
            # rollback; the writable copy is the new root
            path = f"/.snapshots/{num}/snapshot"
            if status.subvol_readonly(path):
                return _("Before rollback")
            if Path(path).is_dir():
                return _("After rollback")
        # Written by nazoos-welcome (root/maintenance.py *_SNAPSHOT)
        elif d == "nazoos-welcome: manual snapshot":
            return _("Manual snapshot")
        elif d.startswith("nazoos-welcome: before switching to "):
            return _("Before channel switch")
        # Made by hand: its own text
        return d or None
    return None


def wait_for_cleanup(timeout=600):
    """snapper-cleanup fails with "Config is locked" when snapshots are
    named while it deletes some (VM 2026-10-19: every hourly run that
    woke nazoos-update-label.path); wait until it has finished."""
    end = time.monotonic() + timeout
    while time.monotonic() < end and capture(
            ["systemctl", "is-active", "--quiet",
             "snapper-cleanup.service"]).returncode == 0:
        time.sleep(2)


def _snapshots_stamp():
    stamp = []
    for p in (Path("/.snapshots"), Path("/.snapshots/grub-snapshot.cfg")):
        try:
            stamp.append(p.stat().st_mtime_ns)
        except OSError:
            stamp.append(None)
    return tuple(stamp)


def wait_quiet(quiet=3, timeout=60):
    """Wait until /.snapshots has not changed for QUIET seconds. A burst
    of snapshot changes (several deleted at once) becomes one run instead
    of one per change, so the service never hits systemd's start limit
    (5 starts in 10 s) and does not lock snapper's config while the user
    is still deleting."""
    end = time.monotonic() + timeout
    stamp = _snapshots_stamp()
    while time.monotonic() < end:
        time.sleep(quiet)
        now = _snapshots_stamp()
        if now == stamp:
            return
        stamp = now


def label_snapshots(update_after=None):
    """Readable boot menu entries. Snapshots of the update that started
    after snapshot UPDATE_AFTER get "Before/After update", other zypper
    pairs "Before/After software change", timeline ones "Automatic", the
    rest their description; always with the local date. Snapshots that
    already have a label are left alone."""
    if not proc.has("snapper"):
        return 0
    wait_for_cleanup()
    with locked(LABEL_LOCK):
        return name_snapshots(update_after)


def name_snapshots(update_after):
    named = 0
    _ = system_translation().gettext
    # xgettext:no-python-format
    date_fmt = _("%Y-%m-%d %H:%M")
    snaps = snapshots()
    zypp_pre = {s["number"] for s in snaps if s["type"] == "pre"
                and (s.get("description") or "").startswith("zypp(")}
    for s in snaps:
        num = s["number"]
        is_update = update_after is not None and num > update_after
        # nazoos-update-label.path may have named the pair of this update
        # "software change" while zypper was running: rename those
        if num == 0 or ("bootloader" in (s.get("userdata") or {})
                        and not is_update):
            continue
        text = snapshot_label(s, zypp_pre, is_update, _)
        if text is None:
            continue
        try:
            date = datetime.strptime(s["date"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
        # snapper splits userdata at "," and "="
        label = (text + " " + date.strftime(date_fmt)) \
            .replace(",", " ").replace("=", " ")
        r = capture(["snapper", "modify", "--userdata",
                     f"bootloader={label}", str(num)])
        if r.returncode != 0:
            say(f"Note: snapshot {num} could not be named: "
                f"{(r.stderr or r.stdout).strip()}")
            continue
        named += 1
    return named


# --- rollback ---------------------------------------------------------------

def rollback(_args):
    num = status.booted_snapshot()
    if not num:
        raise Fail("the system was not started from a snapshot")
    # --ambit classic: also works on installs whose root subvolume is not
    # snapshot 1 (Calamares, ADR 0005). Snapper makes a backup snapshot of
    # the broken state and sets a writable copy of snapshot NUM as default.
    run(["snapper", "--ambit", "classic", "rollback",
         "--description", f"nazoos-update: rollback to {num}"])
    reboot()


def label(_args):
    wait_quiet()
    # The path unit misses changes while this runs (e.g. zypper's post
    # snapshot during our first pass): repeat until a pass names nothing
    for _round in range(10):
        if not label_snapshots():
            break
        time.sleep(2)
