# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Failed systemd units of the system and the user session (no Qt here)."""

import re
import time

from nazoos_common import proc

# Failed units the repair page ignores: known harmless upstream issues.
# drkonqi-coredump-pickup (drkonqi6 6.7): RuntimeMaxSec=30min, ends with
# result "timeout" after login although nothing crashed (VM 2026-10-11)
IGNORED_UNITS = {"drkonqi-coredump-pickup.service"}
# Apps started from the menu run as transient units app-<name>@<id>.service
# (or .scope). One fails when the app exits with an error, e.g. a cancelled
# password dialog of a pkexec launcher: not a system problem, and
# restarting it would start the app again.
# drkonqi-coredump-processor@ hands one crash to DrKonqi and ends with
# result "timeout" after 5 min when nobody picks it up; a crash loop left
# 26 of them (Waydroid in a VM, 2026-10-15). The crash is the problem,
# restarting the unit fixes nothing
IGNORED_UNIT_PATTERN = (r"app-.+@[0-9a-f]+\.(service|scope)"
                        r"|drkonqi-coredump-processor@.+\.service")
# Seconds to wait after restarting failed units: a Type=simple unit
# fails again only after "systemctl restart" has returned
UNIT_SETTLE_SECONDS = 3


def failed_units(user=False):
    units = [line.split()[0] for line in proc.out(
        proc.systemctl(user) + ["list-units", "--failed", "--plain",
                                "--no-legend"]).splitlines() if line.strip()]
    return [u for u in units if u not in IGNORED_UNITS
            and not re.fullmatch(IGNORED_UNIT_PATTERN, u)]


def restart_failed(user, run):
    """Restart the failed units, wait, reset-failed the ones that recovered.
    RUN(cmd) runs one systemctl command. Returns the units still failing."""
    base = proc.systemctl(user)
    units = failed_units(user)
    for unit in units:
        if unit.endswith((".service", ".mount", ".socket")):
            run(base + ["restart", unit])
    if not units:
        return []
    # Check only after a moment, and never reset-failed before: that
    # hid units that fail again right after the restart
    time.sleep(UNIT_SETTLE_SECONDS)
    still = failed_units(user)
    fixed = [u for u in units if u not in still]
    if fixed:
        run(base + ["reset-failed"] + fixed)
    return still
