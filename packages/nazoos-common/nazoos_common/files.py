# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""File helpers shared by the GUIs, the notifier and the root helpers
(atomic replace, flock); no Qt here."""

import contextlib
import fcntl
import os
import stat
import tempfile
from pathlib import Path


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
