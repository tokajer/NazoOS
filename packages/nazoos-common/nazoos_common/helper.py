# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skeleton of the root helpers started via pkexec (no Qt here).

Every user-facing text is an English template for gettext:
Fail("'{cmd}' failed (exit code {rc})", cmd=..., rc=...). The GUI
translates it (errors.py); xgettext collects it with --keyword=Fail.
"""

import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

from . import errors
from .proc import rpm_installed  # noqa: F401 (re-exported for the actions)

# zypper exit codes >= 100 that mean "done, but note this"
# (man zypper, EXIT CODES)
ZYPPER_INFO = {
    102: "restart the computer to finish the update",
    103: "zypper updated itself; run the action again if something is missing",
    106: "some repositories could not be refreshed and were skipped",
}

ZYPPER = ["zypper", "--non-interactive"]
ZYPPER_IN = ZYPPER + ["install", "--auto-agree-with-licenses"]
FLATPAK = ["flatpak", "--system"]
REPOS_DIR = Path("/etc/zypp/repos.d")


class Fail(Exception):
    """An error the user sees: TEMPLATE with {name} fields from PARAMS."""

    def __init__(self, template, **params):
        super().__init__(errors.fill(template, params))
        self.template = template
        self.params = params


class Passthrough(Exception):
    """Ends the action with exit code RC without an own "@@error" line:
    a nested helper has already printed the reason."""

    def __init__(self, rc):
        super().__init__(rc)
        self.rc = rc


def say(text):
    print(text, flush=True)


def run(cmd, check=True, on_line=None):
    """Run CMD with its output in the log. zypper's ZYPPER_INFO codes
    count as success (a note is logged). ON_LINE(text), if given, also
    sees every output line."""
    say("$ " + " ".join(cmd))
    if on_line is None:
        rc = subprocess.run(cmd, stdin=subprocess.DEVNULL).returncode
    else:
        with subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as proc:
            for raw in proc.stdout:
                sys.stdout.buffer.write(raw)
                sys.stdout.flush()
                on_line(raw.decode(errors="replace"))
        rc = proc.returncode
    if cmd[0] == "zypper" and rc in ZYPPER_INFO:
        say(f"Note: {ZYPPER_INFO[rc]}")
        return 0
    if check and rc != 0:
        raise Fail("'{cmd}' failed (exit code {rc})", cmd=cmd[0], rc=rc)
    return rc


def capture(cmd):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def output(cmd):
    return capture(cmd).stdout


def repo_with_url(fragment):
    """Alias of the zypper repo whose .repo file contains FRAGMENT."""
    for f in REPOS_DIR.glob("*.repo"):
        text = f.read_text(errors="replace")
        if fragment in text:
            m = re.search(r"^\[(.+)\]", text, re.M)
            if m:
                return m.group(1)
    return None


def repo_has(alias, name):
    """Package `name` exists in repo `alias` (zypper exit 104: not found)."""
    return subprocess.run(
        ZYPPER + ["--quiet", "search", "--match-exact", "--repo", alias,
                  name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL).returncode == 0


def arg(args, i, allowed=None):
    if len(args) <= i:
        raise Fail("missing argument")
    if allowed is not None and args[i] not in allowed:
        raise Fail("invalid argument: {arg}", arg=args[i])
    return args[i]


def main(actions, lock_timeout, max_args=None, argv=None):
    """Run the action named in ARGV[1] with the rest as arguments; the
    last output line "@@error ..." carries the reason of a failure."""
    argv = sys.argv if argv is None else argv
    if os.geteuid() != 0:
        say(errors.encode("must run as root (via pkexec)"))
        return 1
    if (len(argv) < 2 or argv[1] not in actions
            or (max_args is not None and len(argv) - 2 > max_args)):
        say(errors.encode("unknown action"))
        return 2
    # Wait for a running zypper/PackageKit instead of failing at once
    os.environ["ZYPP_LOCK_TIMEOUT"] = str(lock_timeout)
    os.environ["LC_ALL"] = "C.UTF-8"
    try:
        actions[argv[1]](argv[2:])
    except Passthrough as e:
        return e.rc
    except Fail as e:
        say(errors.encode(e.template, e.params))
        return 1
    except OSError as e:
        say(errors.encode("system error: {detail}", {"detail": str(e)}))
        return 1
    except Exception as e:  # a bug must still reach the user as a message
        traceback.print_exc(file=sys.stdout)
        say(errors.encode("program error: {detail}",
                          {"detail": f"{type(e).__name__}: {e}"}))
        return 1
    return 0
