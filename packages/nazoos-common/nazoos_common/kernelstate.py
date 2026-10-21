# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""State files of the NazoOS kernel opt-in (ADR 0008), no Qt here.

nazoos-welcome's root helper and nazoos-kernel-boot write them,
the GUIs and the update notifier only read.
"""

import json
from pathlib import Path

from . import helper, proc

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
    helper.write_atomic(BOOTS, json.dumps(data))


def stable():
    """kernel-nazoos started cleanly STABLE_BOOTS times in a row and the
    openSUSE kernel is still installed: time to offer stage 2."""
    if not PREFER.exists():
        return False
    if read_boots().get("count", 0) < STABLE_BOOTS:
        return False
    return proc.rpm_installed("kernel-default") and not proc.rpm_installed(
        "nazoos-kernel-only")
