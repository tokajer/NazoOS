# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML pages and the system."""

import glob
import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (Property, QObject, QProcess, QProcessEnvironment,
                            Signal, Slot)
from PySide6.QtGui import QGuiApplication

from . import catalog, system

HELPER = os.environ.get("NAZOOS_WELCOME_HELPER",
                        "/usr/libexec/nazoos-welcome/nazoos-welcome-helper")

# Apps the UI may start: desktop file patterns, then a fallback command
LAUNCHERS = {
    "discover": (["org.kde.discover.desktop"], ["plasma-discover"]),
    "updates": ([], ["plasma-discover", "--mode", "update"]),
    "nazoos-update": (["*nazoos-update*.desktop"], ["nazoos-update"]),
    "myrlyn": (["*myrlyn*sudo*.desktop", "*myrlyn*.desktop"], ["myrlyn"]),
    "btrfs-assistant": (["*btrfs-assistant*.desktop"], ["btrfs-assistant"]),
    "lact": (["*LACT*.desktop", "*lact*.desktop"], ["lact", "gui"]),
    "coolercontrol": (["*coolercontrol*.desktop"], ["coolercontrol"]),
    "steam": (["steam.desktop"], ["steam"]),
    "systemsettings": (["systemsettings.desktop"], ["systemsettings"]),
    "installer": (["nazoos-installer.desktop"], None),
}

# Root actions of the helper, with the text shown while they run
ACTION_LABELS = {
    "codecs-install": "Installing multimedia codecs",
    "nvidia-install": "Installing the NVIDIA driver",
    "scx-enable": "Enabling the scheduler",
    "scx-disable": "Disabling the scheduler",
    "kparam": "Changing kernel options",
    "deck-install": "Installing the handheld pattern",
    "app-install": "Installing",
    "app-remove": "Removing",
    "service": "Changing service",
    "system-update": "Updating the system",
    "repo-refresh": "Refreshing repositories",
    "cache-clean": "Cleaning the package cache",
    "flatpak-unused": "Removing unused Flatpak runtimes",
    "flatpak-repair": "Repairing Flatpak",
    "snapshot": "Creating a snapshot",
    "automount-add": "Adding drive",
    "automount-remove": "Removing drive",
}


def _desktop_file(patterns):
    dirs = [Path.home() / ".local/share"] + [
        Path(d) for d in os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    dirs.append(Path("/var/lib/flatpak/exports/share"))
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
    # action, success, message (already translated)
    actionFinished = Signal(str, bool, str)
    _stateReady = Signal(object)

    def __init__(self, translator):
        super().__init__()
        self._tr = translator
        self._state = {}
        self._busy = False
        self._log = ""
        self._task = ""
        self._proc = None
        self._pending_user_service = None
        self._refreshing = False
        self._stateReady.connect(self._set_state)

    # --- properties ---------------------------------------------------------

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

    def _get_catalog(self):
        return {
            "apps": catalog.APPS,
            "categories": catalog.APP_CATEGORIES,
            "services": catalog.SERVICES,
            "kparams": catalog.KERNEL_PARAMS,
            "schedulers": catalog.SCX_SCHEDULERS,
        }

    catalog = Property("QVariantMap", _get_catalog, constant=True)

    # --- state ----------------------------------------------------------------

    @Slot()
    def refresh(self):
        if self._refreshing:
            return
        self._refreshing = True

        def work():
            try:
                st = system.collect()
            except Exception as e:  # never kill the UI over a probe
                st = dict(self._state, error=str(e))
            self._stateReady.emit(st)

        threading.Thread(target=work, daemon=True).start()

    def _set_state(self, st):
        self._refreshing = False
        self._state = st
        self.stateChanged.emit()

    # --- root actions ---------------------------------------------------------

    def _append(self, text):
        self._log += text
        if len(self._log) > 200_000:
            self._log = self._log[-150_000:]
        self.logChanged.emit()

    @Slot(str, "QVariantList")
    def run(self, action, args):
        if self._busy:
            return
        if action not in ACTION_LABELS:
            return
        args = [str(a) for a in args]
        self._task = self._tr.gettext(ACTION_LABELS[action])
        self._busy = True
        self.busyChanged.emit()
        self._append(f"\n=== {self._task} ===\n")
        self._errline = ""
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(lambda: self._read(proc))
        proc.finished.connect(
            lambda code, status: self._finished(action, args, code, status))
        proc.errorOccurred.connect(
            lambda err: self._failed_start(action, proc, err))
        self._proc = proc
        proc.start("pkexec", [HELPER, action] + args)

    def _read(self, proc):
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            if line.startswith("@@error "):
                self._errline = line[8:]
        self._append(text)

    def _failed_start(self, action, proc, err):
        if err == QProcess.FailedToStart:
            self._done(action, False,
                       self._tr.gettext("pkexec could not be started."))

    def _finished(self, action, args, code, _status):
        if code == 0:
            if self._pending_user_service:
                svc, on = self._pending_user_service
                self._pending_user_service = None
                self._user_service(svc, on)
            self._done(action, True, self._tr.gettext("Done."))
        elif code in (126, 127) and not self._errline:
            # pkexec: dialog dismissed or not authorized
            self._pending_user_service = None
            self._done(action, False,
                       self._tr.gettext("Cancelled: no administrator "
                                        "password was given."))
        else:
            self._pending_user_service = None
            msg = self._tr.gettext("Something went wrong.")
            if self._errline:
                msg += " " + self._errline
            self._done(action, False, msg)

    def _done(self, action, ok, message):
        self._busy = False
        self._task = ""
        self.busyChanged.emit()
        self.actionFinished.emit(action, ok, message)
        self.refresh()

    # --- user-level actions -----------------------------------------------------

    def _user_service(self, svc, on):
        cmd = ["systemctl", "--user", "enable" if on else "disable", "--now",
               svc["unit"]]
        self._append("$ " + " ".join(cmd) + "\n")
        r = subprocess.run(cmd, capture_output=True, text=True)
        self._append(r.stdout + r.stderr)

    @Slot(str, bool)
    def setService(self, service_id, on):
        svc = catalog.by_id(catalog.SERVICES, service_id)
        if svc is None or self._busy:
            return
        installed = self._state.get("services", {}).get(
            service_id, {}).get("installed", False)
        if svc["user"]:
            if installed or not on:
                self._user_service(svc, on)
                self.actionFinished.emit("service", True,
                                         self._tr.gettext("Done."))
                self.refresh()
                return
            self._pending_user_service = (svc, on)
        self.run("service", [service_id, "on" if on else "off"])

    @Slot(bool)
    def setAutostart(self, enabled):
        system.set_autostart(enabled)
        self.refresh()

    @Slot(str)
    def launch(self, launcher_id):
        entry = LAUNCHERS.get(launcher_id)
        if entry is None:
            return
        patterns, fallback = entry
        desktop = _desktop_file(patterns) if patterns else None
        if desktop and shutil.which("kioclient"):
            subprocess.Popen(["kioclient", "exec", desktop],
                             start_new_session=True)
        elif desktop and shutil.which("gio"):
            subprocess.Popen(["gio", "launch", desktop],
                             start_new_session=True)
        elif fallback and shutil.which(fallback[0]):
            subprocess.Popen(fallback, start_new_session=True)
        else:
            self.actionFinished.emit(
                "launch", False,
                self._tr.gettext("This program is not installed."))

    @Slot(result=str)
    def sysinfo(self):
        return system.sysinfo(self._state)

    @Slot()
    def copySysinfo(self):
        QGuiApplication.clipboard().setText(system.sysinfo(self._state))

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)
