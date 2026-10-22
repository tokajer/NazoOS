# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Autostart of the welcome window at login, per user."""

import re
from pathlib import Path

from nazoos_common import proc

NAME = "nazoos-welcome.desktop"


def _file():
    return Path.home() / ".config" / "autostart" / NAME


def enabled():
    if not _file().exists():
        return True
    return not re.search(r"^Hidden\s*=\s*true", proc.read(_file()),
                         re.M | re.I)


def set_enabled(on):
    if on:
        _file().unlink(missing_ok=True)
    else:
        _file().parent.mkdir(parents=True, exist_ok=True)
        # Hidden=true overrides the system-wide autostart entry
        _file().write_text("[Desktop Entry]\nType=Application\n"
                           "Name=NazoOS Welcome\nHidden=true\n")
