# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actions on the user session that need no root rights (no Qt here)."""

import subprocess

from nazoos_common import proc

from .repair_checks import restart_failed

# A unit start that hangs would keep the window busy for good: the
# background thread never returns
USER_UNIT_TIMEOUT = 60


def set_user_unit(unit, on):
    """Enable and start (or disable and stop) the user UNIT, returns the
    log."""
    cmd = proc.systemctl(True) + ["enable" if on else "disable", "--now", unit]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=USER_UNIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"{' '.join(cmd)}: no answer after "
                           f"{USER_UNIT_TIMEOUT} s") from None
    return "$ " + " ".join(cmd) + "\n" + r.stdout + r.stderr


def restart_user_units():
    """Fix part without root: failed units of the user session.
    Returns the log and the units that still fail after the restart."""
    log = []

    def run(cmd):
        log.append("$ " + " ".join(cmd) + "\n" + proc.out(cmd))
    still = restart_failed(True, run)
    return "".join(log), still
