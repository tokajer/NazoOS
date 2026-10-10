# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML window and the system."""

import glob
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QProcess,
                            Signal, Slot)
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
}


def _desktop_file(patterns):
    dirs = [Path.home() / ".local/share"] + [
        Path(d) for d in os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    for pattern in patterns:
        for d in dirs:
            hits = sorted(glob.glob(str(d / "applications" / pattern)))
            if hits:
                return hits[0]
    return None


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
        self._errline = ""
        self._reboot = False
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
        self._errline = ""
        self.busyChanged.emit()
        self._append(f"\n=== {self._task} ===\n")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._read(proc))
        proc.finished.connect(lambda code, _s: self._finished(action, code))
        proc.errorOccurred.connect(lambda err: self._failed_start(action, err))
        self._proc = proc
        proc.start("pkexec", [HELPER, action])

    def _read(self, proc):
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            if line.startswith("@@error "):
                self._errline = line[8:]
            elif line == "@@reboot":
                self._reboot = True
        self._append(text)

    def _failed_start(self, action, err):
        if err == QProcess.FailedToStart:
            self._done(action, False, _("pkexec could not be started."))

    def _finished(self, action, code):
        if code == 0:
            self._done(action, True, _("Done."))
        elif code in (126, 127) and not self._errline:
            self._done(action, False,
                       _("Cancelled: no administrator password was given."))
        else:
            msg = _("Something went wrong.")
            if self._errline:
                msg += " " + self._errline
            self._done(action, False, msg)

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
        patterns, fallback = entry
        desktop = _desktop_file(patterns)
        if desktop and shutil.which("kioclient"):
            subprocess.Popen(["kioclient", "exec", desktop],
                             start_new_session=True)
        elif shutil.which(fallback[0]):
            subprocess.Popen(fallback, start_new_session=True)
        else:
            self.actionFinished.emit("launch", False,
                                     _("This program is not installed."))

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)
