# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML pages and the system."""

import os
import subprocess
import threading
import traceback

from nazoos_common.qt import ActionRunner
from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import catalog, repair, system

# Cheap probes for the card an action changed: read right after it, the
# full system.collect() takes 15-20 s (zypper searches).
# action: (state key, function in system)
QUICK_PROBES = {
    "channel": ("channel", "update_channel"),
    "session-boot-mode": ("session", "session_state"),
    "automount-add": ("drives", "drives"),
    "automount-remove": ("drives", "drives"),
}

HELPER = os.environ.get("NAZOOS_WELCOME_HELPER",
                        "/usr/libexec/nazoos-welcome/nazoos-welcome-helper")


class Backend(ActionRunner):
    stateChanged = Signal()
    canRetryChanged = Signal()
    findingsChanged = Signal()
    # Retry of a failed action that needs the MokManager password again
    mokRetryRequested = Signal(str, "QVariantList")
    # Path of a saved bug report
    reportSaved = Signal(str)
    # Runs a callable on the GUI thread (see _background)
    _call = Signal(object)

    def __init__(self, translator):
        super().__init__(HELPER, translator.gettext, catalog.ACTION_LABELS)
        self._state = {}
        # (action, args, needs MokManager password) of the last run() that
        # "Try again" may repeat, None after anything else
        self._retry = None
        self._on_success = None
        self._refreshing = False
        self._refresh_again = False
        # State keys read by _quick_refresh since the last full refresh
        self._quick = set()
        self._call.connect(lambda f: f())
        # Repair page: None = not checked yet
        self._findings = None
        self._checking = False
        self._reporting = False

    # --- properties ---------------------------------------------------------

    def _get_state(self):
        return self._state

    state = Property("QVariantMap", _get_state, notify=stateChanged)

    def _get_can_retry(self):
        return self._retry is not None

    canRetry = Property(bool, _get_can_retry, notify=canRetryChanged)

    def _set_retry(self, retry):
        changed = (retry is None) != (self._retry is None)
        self._retry = retry
        if changed:
            self.canRetryChanged.emit()

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

    def _quick_refresh(self, action):
        key, probe = QUICK_PROBES[action]
        try:
            value = getattr(system, probe)()
        except Exception:
            traceback.print_exc()
            return
        self._quick.add(key)
        self._state = dict(self._state, **{key: value})
        self.stateChanged.emit()

    def _set_state(self, st):
        self._refreshing = False
        if self._refresh_again:
            # Started before the last action: keep what _quick_refresh read
            st = dict(st, **{k: self._state[k] for k in self._quick
                             if k in self._state})
        else:
            self._quick.clear()
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

    @Slot(bool)
    def fixUnits(self, with_system):
        """Restart failed user units (no root), then the system units."""
        if self._busy:
            return
        self._begin("repair-units")
        self._background(
            repair.restart_user_units,
            lambda r: self._user_units_fixed(with_system, *r),
            lambda e: self._done("repair-units", False, str(e)))

    def _user_units_fixed(self, with_system, log, still):
        self._append(log)
        if with_system:
            # The system units follow, with the password dialog
            self._end_busy()
            self.run("repair-units", [])
        elif still:
            self._done("repair-units", False, self._gettext(
                "These services still fail after a restart: %1")
                .replace("%1", ", ".join(still)))
        else:
            self._done("repair-units", True, self._gettext("Done."))

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
            self._set_retry(None)
            self.actionFinished.emit("report", False, str(e))

        self._background(
            lambda: repair.report(state, findings, log), done, failed)

    # --- root actions ---------------------------------------------------------

    def _begin(self, action):
        self._set_retry(None)
        super()._begin(action)

    @Slot(str, "QVariantList")
    def run(self, action, args, stdin=None, on_success=None):
        """ON_SUCCESS(done), if given, runs after exit code 0 and must
        call done() to finish the task."""
        if self._busy:
            return
        if action not in catalog.ACTION_LABELS:
            return
        self._begin(action)
        # stdin only carries the MokManager password hash (runMok)
        self._set_retry(None if on_success else (
            action, list(args), stdin is not None))
        self._on_success = on_success
        self._start(action, args, stdin)

    @Slot()
    def retry(self):
        if self._busy or self._retry is None:
            return
        action, args, needs_mok = self._retry
        if needs_mok:
            self.mokRetryRequested.emit(action, args)
        else:
            self.run(action, args)

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
            self._set_retry(None)
            self.actionFinished.emit(action, False, self._gettext(
                "The password for the Secure Boot key could not be "
                "prepared (openssl is missing)."))
            return
        self.run(action, args, mok_hash)

    def _helper_finished(self, action, proc, ok, message):
        on_success, self._on_success = self._on_success, None
        if ok and on_success:
            on_success(lambda: self._done(action, True, message))
        else:
            self._done(action, ok, message)

    def _done(self, action, ok, message):
        self._end_busy()
        self.actionFinished.emit(action, ok, message)
        if action in QUICK_PROBES:
            self._quick_refresh(action)
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
                    "service", True, self._gettext("Done.")))
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
        # A failed launch must not offer the earlier action again
        self._set_retry(None)
        super().launch(launcher_id)

    @Slot()
    def copySysinfo(self):
        QGuiApplication.clipboard().setText(self._state.get("sysinfo", ""))
