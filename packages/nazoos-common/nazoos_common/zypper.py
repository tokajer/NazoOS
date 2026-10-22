# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""zypper command lines and exit codes shared by the GUIs' root helpers
and the kernel code (no Qt here)."""

from . import proc

ZYPPER = ["zypper", "--non-interactive"]
ZYPPER_IN = ZYPPER + ["install", "--auto-agree-with-licenses"]

# zypper needs-rebooting / dup exit code: restart needed
NEEDS_REBOOT = 102
# zypper exit codes >= 100 that mean "done, but note this"
# (man zypper, EXIT CODES)
INFO = {
    NEEDS_REBOOT: "restart the computer to finish the update",
    103: "zypper updated itself; run the action again if something is missing",
    106: "some repositories could not be refreshed and were skipped",
}
# "dup --dry-run" / list-updates also end with 100 (updates) or 101 (patches)
OK = (0, 100, 101, *INFO)

# Longer than the helpers' ZYPP_LOCK_TIMEOUT (120/300 s) so a held zypp lock
# is waited for, but a hung zypper cannot block the root action forever
REPO_HAS_TIMEOUT = 360


def repo_has(alias, name):
    """Package `name` exists in repo `alias` (zypper exit 104: not found).
    False as well if zypper is missing (proc.rc: 127) or hangs."""
    return proc.rc(ZYPPER + ["--quiet", "search", "--match-exact", "--repo",
                             alias, name], timeout=REPO_HAS_TIMEOUT) == 0
