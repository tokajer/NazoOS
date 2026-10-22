# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The "@@error" line of the root helpers (ADR 0030).

The helper runs with LC_ALL=C and sends the English template plus its
values as JSON; the GUI translates the template (the gettext msgid) and
fills in the values:

    @@error {"msg": "'{cmd}' failed (exit code {rc})", "args": {"cmd": ...}}
"""

import json
import re

PREFIX = "@@error "
# Line of a helper: the GUI shows the restart hint
REBOOT = "@@reboot"
_FIELD = re.compile(r"\{(\w+)\}")


def fill(template, args):
    """Replace {name} by args[name]; unknown names stay as they are.
    No str.format: a template never reaches attributes of the values."""
    return _FIELD.sub(
        lambda m: str(args[m.group(1)]) if m.group(1) in args
        else m.group(0), template)


def encode(msg, args=None):
    return PREFIX + json.dumps({"msg": msg, "args": args or {}},
                               ensure_ascii=False)


def decode(text):
    """(template, args) from the text after PREFIX. A plain-text line
    (older helper) is its own template."""
    try:
        data = json.loads(text)
    except ValueError:
        return text, {}
    if not isinstance(data, dict) or not isinstance(data.get("msg"), str):
        return text, {}
    args = data.get("args")
    return data["msg"], args if isinstance(args, dict) else {}


def message(text, gettext=lambda s: s):
    """User text for the text after PREFIX, translated with GETTEXT."""
    template, args = decode(text)
    return fill(gettext(template), args)
