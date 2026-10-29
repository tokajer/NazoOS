# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skeleton of the root helpers started via pkexec (no Qt here).

Every user-facing text is an English template for gettext:
Fail("'{cmd}' failed (exit code {rc})", cmd=..., rc=...). The GUI
translates it (errors.py); xgettext collects it with --keyword=Fail.

Root actions: errors raise, and commands have no timeout because zypper
may wait for its lock or the network. Probes that may fail: proc.py.
"""

import os
import subprocess
import sys
import traceback

from . import errors, zypper

FLATPAK = ["flatpak", "--system"]
# Root part of nazoos-update; nazoos-welcome runs it for "Update now"
UPDATE_HELPER = "/usr/libexec/nazoos-update/nazoos-update-helper"


class Fail(Exception):
    """An error the user sees: TEMPLATE with {name} fields from PARAMS.
    RC is the exit code of main()."""

    rc = 1

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


def _drop_output():
    """The reader of our output is gone (window closed, session ended).
    Point stdout and stderr (one pipe for the GUI) at /dev/null so the
    action runs to its end instead of dying on the next write. The GUI
    cannot stop us anyway (we run as root); stopping half-way is what
    breaks a system, e.g. a "zypper dup" in the middle of its rpm
    transaction."""
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.dup2(null, 2)
    os.close(null)


def _write(raw):
    try:
        # Text from print() (e.g. log=print in nazoos-kernel-boot) first
        sys.stdout.flush()
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
    except BrokenPipeError:
        _drop_output()


def say(text, end="\n"):
    """All output of a root action goes through here or run()."""
    # Like print: a file name that is not UTF-8 must not end the helper
    _write(f"{text}{end}".encode(errors="surrogateescape"))


def reboot():
    """Tell the GUI to show the restart hint."""
    say(errors.REBOOT)


def run(cmd, check=True, on_line=None):
    """Run CMD with its output in the log. zypper's INFO codes
    count as success (a note is logged). ON_LINE(text), if given, also
    sees every output line.
    The output always goes through us, never straight to the GUI's pipe:
    if the GUI goes away, the command must not get SIGPIPE (_drop_output)."""
    say("$ " + " ".join(cmd))
    with subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as proc:
        for raw in proc.stdout:
            _write(raw)
            if on_line is not None:
                on_line(raw.decode(errors="replace"))
    rc = proc.returncode
    if cmd[0] == "zypper" and rc in zypper.INFO:
        say(f"Note: {zypper.INFO[rc]}")
        return 0
    if check and rc != 0:
        raise Fail("'{cmd}' failed (exit code {rc})", cmd=cmd[0], rc=rc)
    return rc


def install(args):
    """zypper install ARGS. A failure is retried once after a forced
    refresh: after a Tumbleweed snapshot an old package file is gone
    (download error 404) or a mirror is not synced yet."""
    if run(zypper.ZYPPER_IN + args, check=False) == 0:
        return
    say("Note: installing failed, refreshing the repositories and retrying")
    run(zypper.ZYPPER + ["refresh", "--force"], check=False)
    run(zypper.ZYPPER_IN + args)


def capture(cmd):
    """For root actions: no timeout, errors are not swallowed. Returns the
    CompletedProcess."""
    return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def output(cmd):
    """For root actions: no timeout, errors are not swallowed. Returns
    stdout whatever the exit code."""
    return capture(cmd).stdout


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
        return e.rc
    except OSError as e:
        say(errors.encode("system error: {detail}", {"detail": str(e)}))
        return 1
    except Exception as e:  # a bug must still reach the user as a message
        say(traceback.format_exc(), end="")
        say(errors.encode("program error: {detail}",
                          {"detail": f"{type(e).__name__}: {e}"}))
        return 1
    return 0
