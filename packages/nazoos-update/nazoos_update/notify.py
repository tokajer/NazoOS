# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-update --notify: desktop notifications, run by a user timer.

Reads the status written by the root check and shows at most one
notification per state, with a button that opens the GUI. No Qt here:
notify-send (libnotify) waits for the click and prints the action; that
wait runs in a transient unit per notification (--notify-one).
"""

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from nazoos_common import kernel, proc
from nazoos_common.files import write_atomic

from . import status
from .i18n import _, ngettext

STATE = Path(os.environ.get("XDG_STATE_HOME",
                            Path.home() / ".local/state")) / "nazoos-update"
# Remind again about the same updates after this time
REMIND = 24 * 3600
# Complain about failing checks only after this time without a good one
CHECK_GRACE = 3 * 24 * 3600


def _launch(cmd, token=""):
    """Start the app in its own unit. A child of this oneshot service
    would be killed with the service's cgroup as soon as main() returns
    (start_new_session does not help). Unit name like KDE's app units:
    app-<desktop id>@<id>.service. TOKEN is the XDG activation token of
    the clicked notification, so the window gets focus under Wayland."""
    app = "org.nazoos.welcome" if cmd[0] == "nazoos-welcome" \
        else "org.nazoos.update"
    if shutil.which("systemd-run"):
        env = [f"--setenv=XDG_ACTIVATION_TOKEN={token}"] if token else []
        subprocess.run(["systemd-run", "--user", "--quiet", "--collect",
                        f"--unit=app-{app}@{uuid.uuid4().hex}.service"]
                       + env + ["--"] + cmd)
    else:
        env = dict(os.environ, XDG_ACTIVATION_TOKEN=token) if token else None
        subprocess.Popen(cmd, start_new_session=True, env=env)


def _load():
    try:
        return json.loads((STATE / "notified.json").read_text())
    except (OSError, ValueError):
        return {}


def _save(data):
    # The longest remind time is 7 days; older keys would pile up
    cutoff = int(time.time()) - 8 * 24 * 3600
    data = {k: t for k, t in data.items() if t > cutoff}
    STATE.mkdir(parents=True, exist_ok=True)
    write_atomic(STATE / "notified.json", json.dumps(data))


def _show(n):
    """Show the notification and wait for its button (blocks until it is
    closed); on click start the GUI on its page or command."""
    rd, wr = os.pipe()
    with os.fdopen(rd) as tokens:
        try:
            r = subprocess.run(
                ["notify-send", f"--app-name={_('NazoOS Update')}",
                 f"--icon={n['icon']}", f"--urgency={n['urgency']}",
                 f"--action=open={n['action']}", f"--activation-token-fd={wr}",
                 "--hint=string:desktop-entry:org.nazoos.update",
                 n["title"], n["body"]],
                capture_output=True, text=True, pass_fds=(wr,))
        finally:
            os.close(wr)
        # Empty if the notification server sends no activation token
        token = tokens.read().strip()
    if r.stdout.strip() == "open":
        _launch(n["command"] or ["nazoos-update", "--page", n["page"]],
                token)


def _send(n):
    """Show N unless it was shown within its remind time. The blocking
    notify-send runs in its own unit, so this service ends at once and
    the timer can run again."""
    seen = _load()
    now = int(time.time())
    if seen.get(n["key"], 0) > now - n["remind"]:
        return
    if not shutil.which("notify-send"):
        return
    # Keys only contain [a-z0-9-]. A still open notification with the
    # same key makes this fail every hour: it is shown already.
    # Tied to the graphical session so a logout stops the unit; without
    # a session the start fails and the key stays unseen.
    r = subprocess.run(
        ["systemd-run", "--user", "--quiet", "--collect",
         "-p", "Requisite=graphical-session.target",
         "-p", "PartOf=graphical-session.target",
         "-p", "After=graphical-session.target",
         f"--unit=nazoos-update-notice-{n['key']}.service", "--",
         "nazoos-update", "--notify-one", n["key"]],
        stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        return
    seen[n["key"]] = now
    _save(seen)


def _fingerprint(st):
    items = [f"{p['name']}={p['new']}" for p in st["packages"]] + st["flatpaks"]
    return hashlib.sha1("\n".join(sorted(items)).encode()).hexdigest()[:16]


def _item(key, title, body, action, page, icon="system-software-update",
          urgency="normal", command=None, remind=REMIND):
    return {"key": key, "title": title, "body": body, "action": action,
            "page": page, "icon": icon, "urgency": urgency,
            "command": command, "remind": remind}


def pending(st, now, stage2_ready, has_welcome):
    """The notifications that apply to status ST, as dicts for _send."""
    snap = st["snapshot"]
    if snap:
        return [_item(f"snapshot-{snap}",
                      _("Started from a snapshot"),
                      _("The system runs from an older, read-only "
                        "snapshot. If everything works, you can make this "
                        "state permanent."),
                      _("Make permanent"), "rollback", icon="edit-undo",
                      urgency="critical")]

    items = []
    if st.get("needs_reboot"):
        items.append(_item(f"reboot-{st.get('updated', 0)}",
                           _("Restart required"),
                           _("Updates were installed. Restart the "
                             "computer to use them."),
                           _("Open"), "update", icon="system-reboot"))

    if stage2_ready and has_welcome:
        items.append(_item(
            "kernel-stable",
            _("NazoOS kernel runs stable"),
            _("The NazoOS kernel started cleanly several times in a row. "
              "Remove the openSUSE kernel now?"),
            _("Open"), "", icon="preferences-system-linux",
            command=["nazoos-welcome", "--page", "kernel"],
            remind=7 * 24 * 3600))

    err = st.get("error")
    if err == status.ERROR_CONFLICT:
        items.append(_item(f"conflict-{st.get('checked', 0) // REMIND}",
                           _("Update needs your decision"),
                           _("The update cannot be installed automatically "
                             "because of a package conflict."),
                           _("Fix"), "update", icon="dialog-warning"))
    elif err == status.ERROR_KEY:
        # Will not heal by itself: no grace time
        key = f"key-{st['keys'][0]['fingerprint'][:16].lower()}"
        items.append(_item(key,
                           _("Repository key needs your decision"),
                           _("A package source offers a signing key that "
                             "is not trusted yet. Updates from it are "
                             "blocked until you check the key."),
                           _("Check key"), "" if has_welcome else "update",
                           icon="dialog-warning",
                           command=["nazoos-welcome", "--page", "repair"]
                           if has_welcome else None))
    elif err and now - st.get("last_ok", now) > CHECK_GRACE:
        items.append(_item(f"error-{now // REMIND}",
                           _("Update check does not work"),
                           _("NazoOS could not check for updates for "
                             "several days. Is the computer connected to "
                             "the internet?"),
                           _("Fix"), "update", icon="dialog-warning"))

    if st["count"] and err != status.ERROR_CONFLICT:
        n = st["count"]
        body = ngettext("%d update is ready to install.",
                        "%d updates are ready to install.", n) % n
        items.append(_item(f"updates-{_fingerprint(st)}",
                           _("Updates available"), body,
                           _("Update now"), "update"))
    return items


def _pending_now():
    return pending(status.collect(), int(time.time()), kernel.stage2_due(),
                   shutil.which("nazoos-welcome") is not None)


def main():
    if proc.is_live():
        return 0
    for item in _pending_now():
        _send(item)
    return 0


def notify_one(key):
    """Own unit of one notification (--notify-one): show it and wait."""
    for item in _pending_now():
        if item["key"] == key:
            _show(item)
            break
    return 0
