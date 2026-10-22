# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Start other apps by their desktop file (no Qt here)."""

import glob
import os
import shutil
import subprocess
from pathlib import Path

# Flatpak apps (LACT, CoolerControl) have their desktop files here
FLATPAK_EXPORTS = ["/var/lib/flatpak/exports/share"]


def desktop_file(patterns):
    """First desktop file matching one of PATTERNS in the XDG dirs."""
    dirs = [Path.home() / ".local/share"] + [
        Path(d) for d in os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    dirs += [Path(d) for d in FLATPAK_EXPORTS]
    for pattern in patterns:
        for d in dirs:
            hits = sorted(glob.glob(str(d / "applications" / pattern)))
            if hits:
                return hits[0]
    return None


def launch(patterns, fallback):
    """Start an app by its desktop file (like the menu does), else by
    the FALLBACK command. False if neither is there."""
    desktop = desktop_file(patterns) if patterns else None
    if desktop and shutil.which("kioclient"):
        cmd = ["kioclient", "exec", desktop]
    elif desktop and shutil.which("gio"):
        cmd = ["gio", "launch", desktop]
    elif fallback and shutil.which(fallback[0]):
        cmd = fallback
    else:
        return False
    subprocess.Popen(cmd, start_new_session=True)
    return True


# Apps both UIs may start: desktop file patterns, then a fallback command
COMMON_LAUNCHERS = {
    "myrlyn": (["*myrlyn*sudo*.desktop", "*myrlyn*.desktop"], ["myrlyn"]),
    # btrfs-assistant itself needs root, the launcher asks for it
    "btrfs-assistant": (["*btrfs-assistant*.desktop"],
                        ["btrfs-assistant-launcher"]),
}
