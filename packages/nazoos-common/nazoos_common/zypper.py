# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""zypper command lines and exit codes shared by the GUIs' root helpers
and the kernel code (no Qt here)."""

import subprocess

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


def repo_has(alias, name):
    """Package `name` exists in repo `alias` (zypper exit 104: not found)."""
    return subprocess.run(
        ZYPPER + ["--quiet", "search", "--match-exact", "--repo", alias,
                  name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL).returncode == 0
