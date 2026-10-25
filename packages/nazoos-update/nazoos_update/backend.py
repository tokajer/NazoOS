# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML window and the system."""

import os
import shutil
import subprocess

from nazoos_common.launcher import COMMON_LAUNCHERS
from nazoos_common.qt import ActionRunner, CoalescedLoad
from PySide6.QtCore import (Property, QFileSystemWatcher, QSettings, QTimer,
                            Signal, Slot)

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
    cleanFlatpaksChanged = Signal()

    def __init__(self):
        super().__init__(HELPER, _, ACTION_LABELS, LAUNCHERS)
        self._state = status.collect()
        # A failed load keeps the old state (background prints the error).
        # The lambda looks status.collect up per load (tests replace it)
        self._loader = CoalescedLoad(
            self, lambda: status.collect(), self._loaded,
            lambda _e: None)
        self._reboot = False
        # The snapshot was made permanent; only a restart is left to do
        self._rolled_back = False
        # Remove unused Flatpak runtimes after the update: the user's
        # choice, off by default (~/.config/NazoOS/nazoos-update.conf)
        self._settings = QSettings("NazoOS", "nazoos-update")
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

    def _get_clean_flatpaks(self):
        return self._settings.value("cleanFlatpaks", False, type=bool)

    def _set_clean_flatpaks(self, on):
        if on != self._get_clean_flatpaks():
            self._settings.setValue("cleanFlatpaks", on)
            self.cleanFlatpaksChanged.emit()

    cleanFlatpaks = Property(bool, _get_clean_flatpaks, _set_clean_flatpaks,
                             notify=cleanFlatpaksChanged)

    @Slot()
    def refresh(self):
        self._request()

    def _request(self, after=None):
        """Load the status in a thread. AFTER(), if given, runs once a
        load that started after this call has finished: a load already
        running may predate the status write the caller waits for."""
        if not self._watch.directories() and status.STATUS.parent.is_dir():
            self._watch.addPath(str(status.STATUS.parent))
        self._loader.request(after)

    def _loaded(self, state):
        self._state = state
        self.stateChanged.emit()

    # --- root actions -----------------------------------------------------

    @Slot(str)
    def run(self, action):
        if self._busy or action not in ACTION_LABELS:
            return
        self._begin(action)
        clean = action == "update" and self._get_clean_flatpaks()
        self._start(action, ["clean-flatpaks"] if clean else [])

    def _helper_finished(self, action, helper_proc, ok, message):
        if helper_proc.reboot:
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
