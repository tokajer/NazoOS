# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML pages and the system."""

import os
import subprocess
import threading
import traceback

from nazoos_common.qt import HelperProcess, launch
from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import catalog, repair, system

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
    # Ends the desktop session (nazoos-session)
    "gaming-mode": ([], ["nazoos-session-select", "gaming"]),
}


# Flatpak apps (LACT, CoolerControl) have their desktop files here
FLATPAK_EXPORTS = ["/var/lib/flatpak/exports/share"]


class Backend(QObject):
    stateChanged = Signal()
    busyChanged = Signal()
    logChanged = Signal()
    # action, success, message (already translated)
    actionFinished = Signal(str, bool, str)
    findingsChanged = Signal()
    # Path of a saved bug report
    reportSaved = Signal(str)
    # Runs a callable on the GUI thread (see _background)
    _call = Signal(object)

    def __init__(self, translator):
        super().__init__()
        self._tr = translator
        self._state = {}
        self._busy = False
        self._log = ""
        self._task = ""
        self._proc = None
        self._refreshing = False
        self._refresh_again = False
        self._call.connect(lambda f: f())
        # Repair page: None = not checked yet
        self._findings = None
        self._checking = False
        self._reporting = False

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

    def _get_findings(self):
        return self._findings if self._findings is not None else []

    findings = Property("QVariantList", _get_findings, notify=findingsChanged)

    def _get_checked(self):
        return self._findings is not None

    checked = Property(bool, _get_checked, notify=findingsChanged)

    def _get_checking(self):
        return self._checking

    checking = Property(bool, _get_checking, notify=findingsChanged)

    def _get_catalog(self):
        return {
            "apps": catalog.APPS,
            "categories": catalog.APP_CATEGORIES,
            "services": catalog.SERVICES,
            "kparams": catalog.KERNEL_PARAMS,
            "schedulers": catalog.SCX_SCHEDULERS,
        }

    catalog = Property("QVariantMap", _get_catalog, constant=True)

    def _background(self, work, done, failed):
        """Run WORK in a thread, then DONE(result) on the GUI thread.

        FAILED(exception) runs there instead if WORK raises, so the busy
        flags of the callers cannot get stuck."""
        def target():
            try:
                result = work()
            except Exception as e:
                traceback.print_exc()
                self._call.emit(lambda e=e: failed(e))
                return
            self._call.emit(lambda: done(result))
        threading.Thread(target=target, daemon=True).start()

    # --- state ----------------------------------------------------------------

    @Slot()
    def refresh(self):
        if self._refreshing:
            self._refresh_again = True
            return
        self._refreshing = True

        # never kill the UI over a probe
        self._background(
            system.collect, self._set_state,
            lambda e: self._set_state(dict(self._state, error=str(e))))

    def _set_state(self, st):
        self._refreshing = False
        self._state = st
        self.stateChanged.emit()
        if self._refresh_again:
            self._refresh_again = False
            self.refresh()

    # --- repair page (ADR 0012) ----------------------------------------------

    @Slot()
    def checkSystem(self):
        if self._checking:
            return
        self._checking = True
        self.findingsChanged.emit()

        def failed(e):  # a broken probe is a finding too
            self._set_findings([{"id": "error", "items": [str(e)],
                                 "fix": "", "userOnly": False}])

        self._background(repair.check, self._set_findings, failed)

    def _set_findings(self, found):
        self._checking = False
        self._findings = found
        self.findingsChanged.emit()

    @Slot(str)
    def fix(self, action):
        """Fix one finding. Failed user units need no password."""
        if self._busy:
            return
        if action not in ("repair-units", ""):
            self.run(action, [])
            return
        self._begin("repair-units")
        self._background(
            repair.restart_user_units,
            lambda r: self._user_units_fixed(action, *r),
            lambda e: self._done("repair-units", False, str(e)))

    def _user_units_fixed(self, action, log, still):
        self._append(log)
        if action:
            # The system units follow, with the password dialog
            self._end_busy()
            self.run(action, [])
        elif still:
            self._done("repair-units", False, self._tr.gettext(
                "These services still fail after a restart: %1")
                .replace("%1", ", ".join(still)))
        else:
            self._done("repair-units", True, self._tr.gettext("Done."))

    @Slot()
    def saveReport(self):
        if self._reporting:
            return
        self._reporting = True
        state, findings, log = self._state, self._findings, self._log

        def done(path):
            self._reporting = False
            self.reportSaved.emit(path)

        def failed(e):
            self._reporting = False
            self.actionFinished.emit("report", False, str(e))

        self._background(
            lambda: repair.report(state, findings, log), done, failed)

    # --- root actions ---------------------------------------------------------

    def _append(self, text):
        self._log += text
        if len(self._log) > 200_000:
            self._log = self._log[-150_000:]
        self.logChanged.emit()

    def _begin(self, action):
        self._task = self._tr.gettext(catalog.ACTION_LABELS[action])
        self._busy = True
        self.busyChanged.emit()
        self._append(f"\n=== {self._task} ===\n")

    def _end_busy(self):
        self._busy = False
        self._task = ""
        self.busyChanged.emit()

    @Slot(str, "QVariantList")
    def run(self, action, args, stdin=None, on_success=None):
        """ON_SUCCESS(done), if given, runs after exit code 0 and must
        call done() to finish the task."""
        if self._busy:
            return
        if action not in catalog.ACTION_LABELS:
            return
        self._begin(action)
        proc = HelperProcess(HELPER, self._tr.gettext, self)
        proc.output.connect(self._append)
        proc.finished.connect(
            lambda ok, msg: self._finished(action, ok, msg, on_success))
        self._proc = proc
        proc.start([action, *args], stdin)

    @Slot(str, "QVariantList", str)
    def runMok(self, action, args, password):
        """run() for actions that may queue the Secure Boot key (ADR 0024).
        Only the SHA-512 crypt hash of the MokManager password leaves this
        process, on the helper's stdin (not visible in the process list)."""
        if self._busy:
            return
        try:
            r = subprocess.run(["openssl", "passwd", "-6", "-stdin"],
                               input=password, capture_output=True, text=True)
            mok_hash = r.stdout.strip() if r.returncode == 0 else ""
        except OSError:
            mok_hash = ""
        if not mok_hash.startswith("$6$"):
            self.actionFinished.emit(action, False, self._tr.gettext(
                "The password for the Secure Boot key could not be "
                "prepared (openssl is missing)."))
            return
        self.run(action, args, mok_hash)

    def _finished(self, action, ok, message, then):
        if ok and then:
            then(lambda: self._done(action, True, message))
        else:
            self._done(action, ok, message)

    def _done(self, action, ok, message):
        self._end_busy()
        self.actionFinished.emit(action, ok, message)
        self.refresh()
        if action.startswith("repair-") and self._findings is not None:
            self.checkSystem()

    # --- user-level actions -----------------------------------------------------

    def _user_service(self, svc, on, then):
        cmd = ["systemctl", "--user", "enable" if on else "disable", "--now",
               svc["unit"]]

        def work():
            r = subprocess.run(cmd, capture_output=True, text=True)
            return "$ " + " ".join(cmd) + "\n" + r.stdout + r.stderr

        def done(log):
            self._append(log)
            then()

        self._background(
            work, done, lambda e: self._done("service", False, str(e)))

    @Slot(str, bool)
    def setService(self, service_id, on):
        svc = catalog.by_id(catalog.SERVICES, service_id)
        if svc is None or self._busy:
            return
        installed = self._state.get("services", {}).get(
            service_id, {}).get("installed", False)
        if svc["user"]:
            if installed or not on:
                self._begin("service")
                self._user_service(svc, on, lambda: self._done(
                    "service", True, self._tr.gettext("Done.")))
                return
            self.run("service", [service_id, "on" if on else "off"],
                     on_success=lambda done: self._user_service(
                         svc, on, done))
            return
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
        if not launch(*entry, extra_dirs=FLATPAK_EXPORTS):
            self.actionFinished.emit(
                "launch", False,
                self._tr.gettext("This program is not installed."))

    @Slot()
    def copySysinfo(self):
        QGuiApplication.clipboard().setText(self._state.get("sysinfo", ""))

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)
