# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Skeleton of the root helpers started via pkexec (no Qt here).

Every user-facing text is an English template for gettext:
Fail("'{cmd}' failed (exit code {rc})", cmd=..., rc=...). The GUI
translates it (errors.py); xgettext collects it with --keyword=Fail.

Root actions: errors raise, and commands have no timeout because zypper
may wait for its lock or the network. Probes that may fail: proc.py.
"""

import contextlib
import fcntl
import os
import stat
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from . import errors, zypper

FLATPAK = ["flatpak", "--system"]


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


def reboot():
    """Tell the GUI to show the restart hint."""
    say(errors.REBOOT)


def run(cmd, check=True, on_line=None):
    """Run CMD with its output in the log. zypper's INFO codes
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
    if cmd[0] == "zypper" and rc in zypper.INFO:
        say(f"Note: {zypper.INFO[rc]}")
        return 0
    if check and rc != 0:
        raise Fail("'{cmd}' failed (exit code {rc})", cmd=cmd[0], rc=rc)
    return rc


def write_atomic(path, text, mode=0o644):
    """Replace PATH with TEXT in one step: a crash leaves the old or the
    new file, never half of it. An existing file keeps mode and label."""
    path = Path(os.path.realpath(path))
    label = None
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        try:
            label = os.getxattr(path, "security.selinux")
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        if label is not None:
            # Tumbleweed uses SELinux; a new inode would get the
            # directory's default label
            try:
                os.setxattr(tmp, "security.selinux", label)
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def capture(cmd):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def output(cmd):
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


@contextlib.contextmanager
def locked(path):
    """Exclusive flock on PATH while the block runs; unlocked if PATH
    cannot be opened (no writable /run in an odd chroot)."""
    try:
        f = open(path, "w")
    except OSError:
        yield
        return
    with f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
