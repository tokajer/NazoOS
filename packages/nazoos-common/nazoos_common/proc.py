# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small probes that need no root rights (no Qt here): run a command,
read a file, ask rpm, boot time."""

import shutil
import subprocess
from pathlib import Path


def out(cmd, timeout=30):
    """stdout of CMD, "" if it is missing, fails to start or hangs."""
    if shutil.which(cmd[0]) is None:
        return ""
    try:
        return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True,
                              timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def rc(cmd, timeout=30):
    """Exit code of CMD: 127 if it is missing, 1 on error or timeout."""
    if shutil.which(cmd[0]) is None:
        return 127
    try:
        return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 1


def read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def rpm_installed(name):
    return rc(["rpm", "-q", "--quiet", name]) == 0


def boot_time():
    """Start of the running system (seconds since 1970), or 0."""
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def is_live():
    # nazoos-calamares-config exists only on the live medium
    return Path("/usr/share/calamares/settings.conf").exists()
