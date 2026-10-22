# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML window and the system."""

import os
import shutil
import subprocess

from nazoos_common.qt import COMMON_LAUNCHERS, ActionRunner
from PySide6.QtCore import Property, QFileSystemWatcher, QTimer, Signal, Slot

from . import status
from .i18n import _

HELPER = os.environ.get("NAZOOS_UPDATE_HELPER",
                        "/usr/libexec/nazoos-update/nazoos-update-helper")

ACTION_LABELS = {
    "check": "Checking for updates",
    "update": "Installing updates",
    "rollback": "Making the snapshot permanent",
}

LAUNCHERS = {
    **COMMON_LAUNCHERS,
    "repair": ([], ["nazoos-welcome", "--page", "repair"]),
}


class Backend(ActionRunner):
    stateChanged = Signal()

    def __init__(self):
        super().__init__(HELPER, _, ACTION_LABELS, LAUNCHERS)
        self._state = status.collect()
        self._refreshing = False
        self._refresh_again = False
        # Callbacks for the next load that starts
        self._after = []
        self._reboot = False
        # The snapshot was made permanent; only a restart is left to do
        self._rolled_back = False
        # Reload when the root check writes a new status
        self._watch = QFileSystemWatcher(self)
        self._watch.addPath(str(status.STATUS.parent))
        # One status write is two directory events (tmp file, replace)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self.refresh)
        self._watch.directoryChanged.connect(lambda _p: self._debounce.start())

    def _get_state(self):
        return self._state

    state = Property("QVariantMap", _get_state, notify=stateChanged)

    def _get_reboot(self):
        return self._reboot or bool(self._state.get("needs_reboot"))

    rebootNeeded = Property(bool, _get_reboot, notify=stateChanged)

    def _get_rolled_back(self):
        return self._rolled_back

    rolledBack = Property(bool, _get_rolled_back, notify=stateChanged)

    def _get_can_repair(self):
        # Repair page of nazoos-welcome (ADR 0012)
        return shutil.which("nazoos-welcome") is not None

    canRepair = Property(bool, _get_can_repair, constant=True)

    @Slot()
    def refresh(self):
        self._request()

    def _request(self, after=None):
        """Load the status in a thread. AFTER(), if given, runs once a
        load that started after this call has finished: a load already
        running may predate the status write the caller waits for."""
        if not self._watch.directories() and status.STATUS.parent.is_dir():
            self._watch.addPath(str(status.STATUS.parent))
        if after:
            self._after.append(after)
        if self._refreshing:
            self._refresh_again = True
        else:
            self._load()

    def _load(self):
        self._refreshing = True
        self._refresh_again = False
        callbacks, self._after = self._after, []
        # A failed load keeps the old state (background prints the error)
        self.background(status.collect,
                        lambda st: self._loaded(st, callbacks),
                        lambda _e: self._loaded(None, callbacks))

    def _loaded(self, state, callbacks):
        self._refreshing = False
        if state is not None:
            self._state = state
        self.stateChanged.emit()
        for callback in callbacks:
            callback()
        if self._refresh_again:
            self._load()

    # --- root actions -----------------------------------------------------

    @Slot(str)
    def run(self, action):
        if self._busy or action not in ACTION_LABELS:
            return
        self._begin(action)
        self._start(action, [])

    def _helper_finished(self, action, proc, ok, message):
        if proc.reboot:
            self._reboot = True
        if ok and action == "rollback":
            self._rolled_back = True
        self._done(action, ok, message)

    def _done(self, action, ok, message):
        self._end_busy()
        # The GUI reads the new status when it hears of the end
        self._request(lambda: self.actionFinished.emit(action, ok, message))

    # --- user actions -----------------------------------------------------

    @Slot()
    def reboot(self):
        # Plasma's own restart dialog (saves the session), else logind
        if shutil.which("qdbus6"):
            try:
                if subprocess.run(
                        ["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt",
                         "promptReboot"], capture_output=True,
                        timeout=10).returncode == 0:
                    return
            except (OSError, subprocess.TimeoutExpired):
                pass
        subprocess.Popen(["systemctl", "reboot"], start_new_session=True)
