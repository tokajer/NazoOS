# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Commands and lookups the root actions share."""

import fnmatch
import os
import re
from pathlib import Path

from nazoos_common import proc, repos
from nazoos_common.helper import (  # noqa: F401 (used by the actions)
    FLATPAK, ZYPPER, ZYPPER_IN, Fail, Passthrough, arg, output, repo_has,
    rpm_installed, run, say)

from .. import catalog

FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
RUN_DIR = Path("/run/nazoos-welcome")
ZYPP_LOCKS = Path("/etc/zypp/locks")


def enable_repo(fragment):
    """Alias of the repo whose URL contains FRAGMENT, and whether this
    call switched it on. An already enabled match wins; with none, the
    first match is enabled. (None, False) if there is no match."""
    matches = [(a, e) for a, url, e in repos.repos() if fragment in url]
    for alias, enabled in matches:
        if enabled:
            return alias, False
    if matches:
        run(ZYPPER + ["modifyrepo", "--enable", matches[0][0]])
        return matches[0][0], True
    return None, False


def packman_switch(alias):
    """Switch installed multimedia packages to Packman's builds; if that
    fails, retry with the 32-bit libraries held back at openSUSE."""
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    dup = ZYPPER + ["dist-upgrade", "--auto-agree-with-licenses", "--from",
                    alias, "--allow-vendor-change", "--allow-downgrade"]
    rc = run(dup, check=False)
    if rc == 0:
        return
    # Packman often rebuilds its 32-bit libraries days after the 64-bit
    # ones; until then they need sonames Tumbleweed no longer has. Keep the
    # 32-bit family at openSUSE (a 32-bit/64-bit mix is harmless).
    # A lock the user set stays: only add (and later remove) our own
    locked = re.findall(r"^solvable_name:\s*(\S+)", proc.read(ZYPP_LOCKS),
                        re.M)
    held = [n for n in held_32bit(output(["rpm", "-qa", "--qf", "%{NAME}\n"]))
            if not any(fnmatch.fnmatchcase(n, pat) for pat in locked)]
    if not held:
        raise Fail("'{cmd}' failed (exit code {rc})", cmd="zypper", rc=rc)
    say("Retrying without the 32-bit libraries: " + " ".join(held))
    run(ZYPPER + ["addlock"] + held)
    try:
        run(dup)
    finally:
        run(ZYPPER + ["removelock"] + held, check=False)


def held_32bit(rpm_names):
    """Installed 32-bit packages of the Packman family, from rpm -qa."""
    family = re.compile(catalog.PACKMAN_FAMILY)
    return sorted({n for n in rpm_names.split()
                   if n.endswith("-32bit") and family.fullmatch(n)})


def flathub_ensure():
    run(FLATPAK + ["remote-add", "--if-not-exists", "flathub", FLATHUB_URL])


def caller():
    """(uid, name) of the user who started the helper via pkexec."""
    uid = int(os.environ.get("PKEXEC_UID", "-1"))
    name = output(["id", "-nu", str(uid)]).strip()
    if uid < 1000 or not name:
        raise Fail("unknown user")
    return uid, name


def running_nazoos():
    return os.uname().release.endswith("-nazoos")
