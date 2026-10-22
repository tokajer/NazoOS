# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Gaming mode (nazoos-session)."""

from pathlib import Path

from nazoos_common import helper

from .. import catalog
from .base import Fail, arg, caller


def session_boot_mode(args):
    """Start in Steam's gaming mode (autologin of the calling user) or
    with the normal login screen (nazoos-session-ctl)."""
    mode = arg(args, 0, ("gaming", "desktop"))
    if not Path(catalog.SESSION_CTL).exists():
        raise Fail("gaming mode is not installed (nazoos-session)")
    if mode == "gaming":
        helper.run([catalog.SESSION_CTL, "boot-mode", "gaming",
                    caller()[1]])
    else:
        helper.run([catalog.SESSION_CTL, "boot-mode", "desktop"])
