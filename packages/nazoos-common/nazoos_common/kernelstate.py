# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""State files of the NazoOS kernel opt-in (ADR 0008), no Qt here.

nazoos-welcome's root helper and nazoos-kernel-boot write them,
the GUIs and the update notifier only read.
"""

import json
import subprocess
from pathlib import Path

STATE = Path("/var/lib/nazoos")
# Exists while the user wants kernel-nazoos as the default boot entry
PREFER = STATE / "kernel-prefer"
# Boot counter, written by nazoos-kernel-boot.service
BOOTS = STATE / "kernel-boots.json"
# Written by the helper when it queues the Secure Boot key. MokNew is
# readable only by root, so the GUI cannot see the request itself; it
# lives until the next boot (shim runs MokManager and deletes it)
MOK_REQUESTED = STATE / "mok-requested"
# Clean boots of kernel-nazoos before stage 2 is offered
STABLE_BOOTS = 3


def read_boots():
    try:
        return json.loads(BOOTS.read_text())
    except (OSError, ValueError):
        return {}


def write_boots(data):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = BOOTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.chmod(0o644)
    tmp.replace(BOOTS)


def _installed(name):
    return subprocess.run(["rpm", "-q", "--quiet", name],
                          stdin=subprocess.DEVNULL).returncode == 0


def stable():
    """kernel-nazoos started cleanly STABLE_BOOTS times in a row and the
    openSUSE kernel is still installed: time to offer stage 2."""
    if not PREFER.exists():
        return False
    if read_boots().get("count", 0) < STABLE_BOOTS:
        return False
    return _installed("kernel-default") and not _installed(
        "nazoos-kernel-only")
