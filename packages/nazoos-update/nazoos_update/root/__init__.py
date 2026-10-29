# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-update, run by helper/nazoos-update-helper."""

import contextlib
import fcntl
import time

from nazoos_common.helper import say

from . import check, snapshots, update

# check and update one at a time: the zypp lock ends with the dry run, and
# a timer check whose Flatpak query outlasts an update would write its
# pre-update package list over the update's status. rollback and label
# write neither (the path unit starts label during an update's snapshots)
ACTION_LOCK = "/run/nazoos-update-action.lock"
# flatpak remote-ls has no timeout: a hanging check must not block updates
# for good, after this the update goes on as before the lock existed
UPDATE_WAIT = 600


@contextlib.contextmanager
def _one_at_a_time(wait):
    """True while holding ACTION_LOCK (or without a writable /run, like
    nazoos_common.files.locked), False after WAIT seconds without it."""
    try:
        f = open(ACTION_LOCK, "w")
    except OSError:
        yield True
        return
    with f:
        deadline = time.monotonic() + wait
        got = said = False
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                got = True
                break
            except BlockingIOError:
                pass
            if time.monotonic() >= deadline:
                break
            if not said:
                say("Waiting for the running update check to finish")
                said = True
            time.sleep(1)
        yield got


def _check(args):
    # Never waits: whatever holds the lock writes a fresh status when it
    # ends. A waiting check could also deadlock against an update that
    # restarts nazoos-update-check.service from its package scripts
    with _one_at_a_time(0) as got:
        if not got:
            say("An update or another check is running: nothing to do")
            return
        check.check(args)


def _update(args):
    with _one_at_a_time(UPDATE_WAIT) as got:
        if not got:
            say("Note: the update check is still running, updating anyway")
        update.update(args)


ACTIONS = {"check": _check, "update": _update,
           "rollback": snapshots.rollback, "label": snapshots.label}
