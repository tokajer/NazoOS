# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-update --notify: desktop notifications, run by a user timer.

Reads the status written by the root check and shows at most one
notification per state, with a button that opens the GUI. No Qt here:
notify-send (libnotify) waits for the click and prints the action.
"""

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import status
from .i18n import _, ngettext

STATE = Path(os.environ.get("XDG_STATE_HOME",
                            Path.home() / ".local/state")) / "nazoos-update"
# Remind again about the same updates after this time
REMIND = 24 * 3600
# Complain about failing checks only after this time without a good one
CHECK_GRACE = 3 * 24 * 3600

_threads = []


def _load():
    try:
        return json.loads((STATE / "notified.json").read_text())
    except (OSError, ValueError):
        return {}


def _save(data):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "notified.json").write_text(json.dumps(data))


def _send(key, title, body, action, page, icon="system-software-update",
          urgency="normal", command=None, remind=REMIND):
    """Show a notification; on click start the GUI on PAGE (or COMMAND)."""
    seen = _load()
    now = int(time.time())
    if seen.get(key, 0) > now - remind:
        return
    seen[key] = now
    _save(seen)
    if not shutil.which("notify-send"):
        return

    # notify-send blocks until the notification is closed: one thread
    # per notification, so several can be shown at the same time
    def wait():
        r = subprocess.run(
            ["notify-send", "--app-name=NazoOS Update", f"--icon={icon}",
             f"--urgency={urgency}", f"--action=open={action}",
             "--hint=string:desktop-entry:org.nazoos.update", title, body],
            capture_output=True, text=True)
        if r.stdout.strip() == "open":
            subprocess.Popen(command or ["nazoos-update", "--page", page],
                             start_new_session=True)

    t = threading.Thread(target=wait)
    t.start()
    _threads.append(t)


def _fingerprint(st):
    items = [f"{p['name']}={p['new']}" for p in st["packages"]] + st["flatpaks"]
    return hashlib.sha1("\n".join(sorted(items)).encode()).hexdigest()[:16]


def main():
    if status.is_live():
        return 0
    st = status.collect()

    snap = st["snapshot"]
    if snap:
        _send(f"snapshot-{snap}",
              _("Started from a snapshot"),
              _("The system runs from an older, read-only snapshot. If "
                "everything works, you can make this state permanent."),
              _("Make permanent"), "rollback", icon="edit-undo",
              urgency="critical")
        for t in _threads:
            t.join()
        return 0

    if st.get("needs_reboot"):
        _send(f"reboot-{st.get('updated', 0)}",
              _("Restart required"),
              _("Updates were installed. Restart the computer to use "
                "them."),
              _("Open"), "update", icon="system-reboot")

    if status.kernel_stable() and shutil.which("nazoos-welcome"):
        _send("kernel-stable",
              _("NazoOS kernel runs stable"),
              _("The NazoOS kernel started cleanly several times in a row. "
                "Remove the openSUSE kernel now?"),
              _("Open"), "", icon="preferences-system-linux",
              command=["nazoos-welcome", "--page", "kernel"],
              remind=7 * 24 * 3600)

    now = int(time.time())
    err = st.get("error")
    if err == "conflict":
        _send(f"conflict-{st.get('checked', 0) // REMIND}",
              _("Update needs your decision"),
              _("The update cannot be installed automatically because "
                "of a package conflict."),
              _("Fix"), "update", icon="dialog-warning")
    elif err and now - st.get("last_ok", now) > CHECK_GRACE:
        _send(f"error-{now // REMIND}",
              _("Update check does not work"),
              _("NazoOS could not check for updates for several days. "
                "Is the computer connected to the internet?"),
              _("Fix"), "update", icon="dialog-warning")

    if st["count"] and err != "conflict":
        n = st["count"]
        body = ngettext("%d update is ready to install.",
                        "%d updates are ready to install.", n) % n
        _send(f"updates-{_fingerprint(st)}", _("Updates available"), body,
              _("Update now"), "update")
    for t in _threads:
        t.join()
    return 0
