# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML window and the system."""

import os
import shutil
import subprocess

from nazoos_common.qt import ActionRunner
from PySide6.QtCore import Property, QFileSystemWatcher, Signal, Slot

from . import status
from .i18n import _

HELPER = os.environ.get("NAZOOS_UPDATE_HELPER",
                        "/usr/libexec/nazoos-update/nazoos-update-helper")

ACTION_LABELS = {
    "check": "Checking for updates",
    "update": "Installing updates",
    "rollback": "Making the snapshot permanent",
}


class Backend(ActionRunner):
    stateChanged = Signal()

    def __init__(self):
        super().__init__(HELPER, _, ACTION_LABELS)
        self._state = {}
        self._reboot = False
        # The snapshot was made permanent; only a restart is left to do
        self._rolled_back = False
        # Reload when the root check writes a new status
        self._watch = QFileSystemWatcher(self)
        self._watch.addPath(str(status.STATUS.parent))
        self._watch.directoryChanged.connect(lambda _p: self.refresh())

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
        if not self._watch.directories() and status.STATUS.parent.is_dir():
            self._watch.addPath(str(status.STATUS.parent))
        self._state = status.collect()
        self.stateChanged.emit()

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
        self.refresh()
        self.actionFinished.emit(action, ok, message)

    # --- user actions -----------------------------------------------------

    @Slot()
    def reboot(self):
        # Plasma's own restart dialog (saves the session), else logind
        if shutil.which("qdbus6") and subprocess.run(
                ["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt",
                 "promptReboot"], capture_output=True).returncode == 0:
            return
        subprocess.Popen(["systemctl", "reboot"], start_new_session=True)
