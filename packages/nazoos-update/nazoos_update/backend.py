# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML window and the system."""

import os
import shutil
import subprocess

from nazoos_common.qt import HelperProcess, launch
from PySide6.QtCore import Property, QFileSystemWatcher, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import status
from .i18n import _

HELPER = os.environ.get("NAZOOS_UPDATE_HELPER",
                        "/usr/libexec/nazoos-update/nazoos-update-helper")

ACTION_LABELS = {
    "check": "Checking for updates",
    "update": "Installing updates",
    "rollback": "Making the snapshot permanent",
}

# Apps the window may start: desktop file patterns, then a command
LAUNCHERS = {
    "btrfs-assistant": (["*btrfs-assistant*.desktop"],
                        ["btrfs-assistant-launcher"]),
    "myrlyn": (["*myrlyn*sudo*.desktop", "*myrlyn*.desktop"], ["myrlyn"]),
    "discover": (["org.kde.discover.desktop"], ["plasma-discover"]),
    "repair": ([], ["nazoos-welcome", "--page", "repair"]),
}


class Backend(QObject):
    stateChanged = Signal()
    busyChanged = Signal()
    logChanged = Signal()
    actionFinished = Signal(str, bool, str)

    def __init__(self):
        super().__init__()
        self._state = {}
        self._busy = False
        self._task = ""
        self._log = ""
        self._reboot = False
        # The snapshot was made permanent; only a restart is left to do
        self._rolled_back = False
        self._proc = None
        # Reload when the root check writes a new status
        self._watch = QFileSystemWatcher(self)
        self._watch.addPath(str(status.STATUS.parent))
        self._watch.directoryChanged.connect(lambda _p: self.refresh())

    def _get_state(self):
        return self._state

    state = Property("QVariantMap", _get_state, notify=stateChanged)

    def _get_busy(self):
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_task(self):
        return self._task

    task = Property(str, _get_task, notify=busyChanged)

    def _get_log(self):
        return self._log

    log = Property(str, _get_log, notify=logChanged)

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

    def _append(self, text):
        self._log += text
        if len(self._log) > 300_000:
            self._log = self._log[-200_000:]
        self.logChanged.emit()

    @Slot(str)
    def run(self, action):
        if self._busy or action not in ACTION_LABELS:
            return
        self._task = _(ACTION_LABELS[action])
        self._busy = True
        self.busyChanged.emit()
        self._append(f"\n=== {self._task} ===\n")
        proc = HelperProcess(HELPER, _, self)
        proc.output.connect(self._append)
        proc.finished.connect(
            lambda ok, msg: self._finished(action, proc, ok, msg))
        self._proc = proc
        proc.start([action])

    def _finished(self, action, proc, ok, message):
        if proc.reboot:
            self._reboot = True
        if ok and action == "rollback":
            self._rolled_back = True
        self._done(action, ok, message)

    def _done(self, action, ok, message):
        self._busy = False
        self._task = ""
        self.busyChanged.emit()
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

    @Slot(str)
    def launch(self, launcher_id):
        entry = LAUNCHERS.get(launcher_id)
        if entry is None:
            return
        if not launch(*entry):
            self.actionFinished.emit("launch", False,
                                     _("This program is not installed."))

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)
