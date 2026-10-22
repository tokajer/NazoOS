# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shell-style KEY=VALUE config files (grub defaults, scx). No Qt, no
subprocess."""

import re


def set_var(text, name, value):
    """Set NAME=VALUE in shell-style config TEXT; VALUE None removes it."""
    line = f"{name}={value}" if value is not None else None
    key = re.escape(name)
    if re.search(rf"^{key}=", text, re.M):
        # A function, so backslashes in VALUE are not read as escapes
        return re.sub(rf"^{key}=.*\n?", lambda _m: line + "\n" if line else "",
                      text, flags=re.M)
    if not line:
        return text
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def get_var(text, name):
    """Value of the last NAME=... line in shell-style TEXT, quotes removed;
    "" if missing. The file is data: never sourced."""
    found = re.findall(
        rf"^[ \t]*{re.escape(name)}[ \t]*=[ \t]*"
        r"""(?:"([^"\n]*)"|'([^'\n]*)'|([^\s#'"]*))[ \t]*(?:#[^\n]*)?\r?$""",
        text, re.M)
    return "".join(found[-1]) if found else ""
