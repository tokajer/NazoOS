# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actions on the user session that need no root rights (no Qt here)."""

import subprocess
import time

from nazoos_common import proc

from .repair_checks import UNIT_SETTLE_SECONDS, failed_units


def set_user_unit(unit, on):
    """Enable and start (or disable and stop) the user UNIT, returns the
    log."""
    cmd = ["systemctl", "--user", "enable" if on else "disable", "--now",
           unit]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return "$ " + " ".join(cmd) + "\n" + r.stdout + r.stderr


def restart_user_units():
    """Fix part without root: failed units of the user session.
    Returns the log and the units that still fail after the restart."""
    log = ""
    units = failed_units(user=True)
    for unit in units:
        log += f"$ systemctl --user restart {unit}\n"
        log += proc.out(["systemctl", "--user", "restart", unit])
    if not units:
        return log, []
    time.sleep(UNIT_SETTLE_SECONDS)
    still = failed_units(user=True)
    fixed = [u for u in units if u not in still]
    if fixed:
        proc.out(["systemctl", "--user", "reset-failed"] + fixed)
    return log, still

