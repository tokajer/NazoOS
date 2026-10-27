# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Switching the multimedia packages to Packman's builds."""

import fnmatch
import re
from pathlib import Path

from nazoos_common import helper, proc
from nazoos_common.helper import Fail, say
from nazoos_common.zypper import ZYPPER

from .. import system
from .base import installed_names

ZYPP_LOCKS = Path("/etc/zypp/locks")
# Tries of the Packman dist-upgrade, the first one included
PACKMAN_TRIES = 3
# "nothing provides 'x' needed by the to be installed PKG" and
# "the to be installed PKG requires 'x', but this requirement cannot be
# provided"
_NEEDED_BY = re.compile(r"needed by the to be installed (\S+)")
_REQUIRES = re.compile(r"the to be installed (\S+) requires .*cannot be "
                       r"provided")
# Matches: libfoo1-1.2-3.1.x86_64
_NEVRA = re.compile(r"([A-Za-z0-9].*)-[^-]+-[^-]+\.(?:x86_64|i586|i686|noarch)")


def unresolvable(text):
    """Sorted names of the packages that zypper's solver output TEXT says
    cannot be installed because something they need is missing."""
    # SHORTCUT: scrapes the English solver text (the helper sets
    # LC_ALL=C.UTF-8); if zypper rewords it nothing is found and the
    # plain zypper error is shown. Revisit when a retry stops working.
    names = set()
    for line in text.splitlines():
        m = _NEEDED_BY.search(line) or _REQUIRES.search(line)
        n = m and _NEVRA.fullmatch(m.group(1).rstrip(".,;"))
        if n:
            names.add(n.group(1))
    return sorted(names)


def _lock_names(name):
    """NAME and its other word size: Packman may lack either build."""
    other = name.removesuffix("-32bit") if name.endswith("-32bit") \
        else name + "-32bit"
    return [name, other]


def held_32bit(names):
    """Installed 32-bit packages of the Packman family out of NAMES."""
    family = re.compile(system.PACKMAN_FAMILY)
    return sorted({n for n in names
                   if n.endswith("-32bit") and family.fullmatch(n)})


def packman_switch(alias):
    """Switch installed multimedia packages to Packman's builds; if that
    fails, retry with the packages that cannot be installed (and on the
    first retry the 32-bit libraries) held back at openSUSE."""
    helper.run(ZYPPER + ["refresh", alias])
    dup = ZYPPER + ["dist-upgrade", "--auto-agree-with-licenses", "--from",
                    alias, "--allow-vendor-change", "--allow-downgrade"]
    lines = []

    def keep(line):
        if "to be installed" in line:
            lines.append(line)
    rc = helper.run(dup, check=False, on_line=keep)
    if rc == 0:
        return
    # Packman often rebuilds its 32-bit libraries days after the 64-bit
    # ones; until then they need sonames Tumbleweed no longer has. Keep the
    # 32-bit family at openSUSE (a 32-bit/64-bit mix is harmless). The same
    # goes for any package the solver reports as unresolvable.
    # A lock the user set stays: only add (and later remove) our own
    locked = re.findall(r"^solvable_name:\s*(\S+)", proc.read(ZYPP_LOCKS),
                        re.M)
    held, broken, last = [], set(), []
    try:
        for attempt in range(PACKMAN_TRIES - 1):
            names = unresolvable("".join(lines))
            broken.update(names)
            want = {n for name in names for n in _lock_names(name)}
            if attempt == 0:
                want.update(held_32bit(installed_names()))
            new = sorted(n for n in want if n not in held
                         and not any(fnmatch.fnmatchcase(n, pat)
                                     for pat in locked))
            if not new:
                break
            say("Retrying without: " + " ".join(new))
            helper.run(ZYPPER + ["addlock"] + new)
            held += new
            lines.clear()
            rc = helper.run(dup, check=False, on_line=keep)
            if rc == 0:
                say("Kept at openSUSE for now: " + " ".join(sorted(broken)))
                return
        last = unresolvable("".join(lines))
        broken.update(last)
    finally:
        if held:
            helper.run(ZYPPER + ["removelock"] + held, check=False)
    # Only when the last try still failed on missing parts: another reason
    # (a conflict, a broken download) must not read as "Packman rebuilds"
    if last:
        raise Fail("Packman is rebuilding some packages ({packages}); "
                   "try again in a few days",
                   packages=", ".join(sorted(broken)))
    raise Fail("'{cmd}' failed (exit code {rc})", cmd="zypper", rc=rc)
