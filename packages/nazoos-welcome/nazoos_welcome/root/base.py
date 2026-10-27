# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Commands and lookups the root actions share."""

import contextlib
import os
from pathlib import Path

from nazoos_common import helper, repos
from nazoos_common.helper import FLATPAK, Fail
from nazoos_common.zypper import ZYPPER

FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
RUN_DIR = Path("/run/nazoos-welcome")


def enable_repo(fragment):
    """Alias of the repo whose URL contains FRAGMENT, and whether this
    call switched it on. An already enabled match wins; with none, the
    first match is enabled. (None, False) if there is no match."""
    matches = [(a, e) for a, url, e in repos.repos() if fragment in url]
    for alias, enabled in matches:
        if enabled:
            return alias, False
    if matches:
        helper.run(ZYPPER + ["modifyrepo", "--enable", matches[0][0]])
        return matches[0][0], True
    return None, False


@contextlib.contextmanager
def repo_in_use(fragment, alias, addrepo_args, keep, key):
    """Alias of the repo whose URL contains FRAGMENT; added as ALIAS with
    ADDREPO_ARGS (options and URL) if there is none. KEY is the shipped
    signing key file of that repo. If the block raises, a repo this call
    switched on is switched off again and one it added is removed, unless
    KEEP() says packages from it are installed."""
    # Only the pinned key is trusted, never what the server sends
    # (ADR 0031). Importing a key rpm already has changes nothing; a key
    # left behind when the steps below fail is still the right one.
    helper.run(["rpm", "--import", str(key)])
    found, enabled = enable_repo(fragment)
    alias = found or alias
    if not found:
        helper.run(ZYPPER + ["addrepo"] + addrepo_args + [alias])
        try:
            helper.run(ZYPPER + ["refresh", alias])
        except Exception:
            # Nothing can be installed from a repo whose key does not match
            helper.run(ZYPPER + ["removerepo", alias], check=False)
            raise
    try:
        if found:
            helper.run(ZYPPER + ["refresh", alias])
        yield alias
    except Exception:
        # No half state
        if enabled:
            helper.run(ZYPPER + ["modifyrepo", "--disable", found],
                       check=False)
        elif not found and not keep():
            helper.run(ZYPPER + ["removerepo", alias], check=False)
        raise


def installed_names(*patterns):
    """Names of the installed packages (rpm -qa), only those matching the
    globs if given."""
    return helper.output(
        ["rpm", "-qa", "--qf", "%{NAME}\n", *patterns]).split()


def flathub_ensure():
    helper.run(FLATPAK + ["remote-add", "--if-not-exists", "flathub",
                          FLATHUB_URL])


def caller():
    """(uid, name) of the user who started the helper via pkexec."""
    uid = int(os.environ.get("PKEXEC_UID", "-1"))
    name = helper.output(["id", "-nu", str(uid)]).strip()
    if uid < 1000 or not name:
        raise Fail("unknown user")
    return uid, name

