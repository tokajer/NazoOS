# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML pages and the system."""

import os
import sys
import traceback

from nazoos_common import mok
from nazoos_common.launcher import COMMON_LAUNCHERS
from nazoos_common.qt import ActionRunner, CoalescedLoad
from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import autostart, catalog, probes, report, user_actions

# Cheap probes for the card an action changed: read right after it, the
# full probes.collect() takes 15-20 s (zypper searches).
# action: (state key, probe function)
QUICK_PROBES = {
    "channel": ("channel", probes.update_channel),
    "session-boot-mode": ("session", probes.session_state),
    "automount-add": ("drives", probes.drives),
    "automount-remove": ("drives", probes.drives),
}

# Apps the pages may start: desktop file patterns, then a fallback command
LAUNCHERS = {
    **COMMON_LAUNCHERS,
    "discover": (["org.kde.discover.desktop"], ["plasma-discover"]),
    "updates": ([], ["plasma-discover", "--mode", "update"]),
    "nazoos-update": (["*nazoos-update*.desktop"], ["nazoos-update"]),
    "lact": (["*LACT*.desktop", "*lact*.desktop"], ["lact", "gui"]),
    "coolercontrol": (["*coolercontrol*.desktop"], ["coolercontrol"]),
    "systemsettings": (["systemsettings.desktop"], ["systemsettings"]),
    "installer": (["nazoos-installer.desktop"], None),
    # Ends the desktop session (nazoos-session)
    "gaming-mode": ([], ["nazoos-session-select", "gaming"]),
}

HELPER = os.environ.get("NAZOOS_WELCOME_HELPER",
                        "/usr/libexec/nazoos-welcome/nazoos-welcome-helper")


class Backend(ActionRunner):
    stateChanged = Signal()
    canRetryChanged = Signal()
    # Retry of a failed action that needs the MokManager password again
    mokRetryRequested = Signal(str, "QVariantList")

    def __init__(self, translator):
        super().__init__(HELPER, translator.gettext, catalog.ACTION_LABELS,
                         LAUNCHERS)
        self._state = {}
        # (action, args, needs MokManager password) of the last run() that
        # "Try again" may repeat, None after anything else
        self._retry = None
        self._on_success = None
        # Never kill the UI over a probe
        self._loader = CoalescedLoad(
            self, report.collect_state, self._set_state,
            lambda e: self._set_state(dict(self._state, error=str(e))))
        # State keys read by _quick_refresh since the last full refresh
        self._quick = set()

    # --- properties ---------------------------------------------------------

    def _get_state(self):
        return self._state

    state = Property("QVariantMap", _get_state, notify=stateChanged)

    def _get_can_retry(self):
        return self._retry is not None

    canRetry = Property(bool, _get_can_retry, notify=canRetryChanged)

    def report_error(self, action, message):
        """Show MESSAGE as failure of ACTION; an earlier action is not
        offered again. Not a Slot."""
        self._set_retry(None)
        self.actionFinished.emit(action, False, message)

    def _set_retry(self, retry):
        changed = (retry is None) != (self._retry is None)
        self._retry = retry
        if changed:
            self.canRetryChanged.emit()

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
        self._loader.request()

    def _quick_refresh(self, action):
        key, probe = QUICK_PROBES[action]
        try:
            value = probe()
        except Exception:
            traceback.print_exc()
            return
        self._quick.add(key)
        self._state = dict(self._state, **{key: value})
        self.stateChanged.emit()

    def _set_state(self, st):
        if self._loader.pending:
            # Started before the last action: keep what _quick_refresh read
            st = dict(st, **{k: self._state[k] for k in self._quick
                             if k in self._state})
        else:
            self._quick.clear()
        self._state = st
        self.stateChanged.emit()

    # --- repair page (ADR 0012): units are root actions, the rest is
    # RepairModel

    @Slot(bool)
    def fixUnits(self, with_system):
        """Restart failed user units (no root), then the system units."""
        if self._busy:
            return
        self._begin("repair-units")
        self.background(
            user_actions.restart_user_units,
            lambda r: self._user_units_fixed(with_system, *r),
            lambda e: self._done("repair-units", False, str(e)))

    def _user_units_fixed(self, with_system, log, still):
        self._append(log)
        if with_system:
            # The system units follow, with the password dialog
            self._launch("repair-units", [], None, None)
        elif still:
            self._done("repair-units", False, self._gettext(
                "These services still fail after a restart: %1")
                .replace("%1", ", ".join(still)))
        else:
            self._done("repair-units", True, self._gettext("Done."))

    # --- root actions ---------------------------------------------------------

    def _begin(self, action):
        self._set_retry(None)
        super()._begin(action)

    @Slot(str, "QVariantList")
    def run(self, action, args):
        self._run(action, args)

    def _run(self, action, args, stdin=None, on_success=None):
        """ON_SUCCESS(done), if given, runs after exit code 0 and must
        call done() to finish the task."""
        if self._busy:
            return
        if action not in catalog.ACTION_LABELS:
            # A programming error in QML: leave a trace in the journal
            print(f"nazoos-welcome: unknown action {action}", file=sys.stderr)
            return
        self._begin(action)
        self._launch(action, args, stdin, on_success)

    def _launch(self, action, args, stdin, on_success):
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
            self._run(action, args)

    @Slot(str, "QVariantList", str)
    def runMok(self, action, args, password):
        """run() for actions that may queue the Secure Boot key (ADR 0024).
        Only the SHA-512 crypt hash of the MokManager password leaves this
        process, on the helper's stdin (not visible in the process list)."""
        if self._busy:
            return
        mok_hash = mok.password_hash(password)
        if not mok_hash:
            self.report_error(action, self._gettext(
                "The password for the Secure Boot key could not be "
                "prepared (openssl is missing)."))
            return
        self._run(action, args, mok_hash)

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

    # --- user-level actions -----------------------------------------------------

    def _user_service(self, svc, on, then):
        def done(log):
            self._append(log)
            then()

        self.background(
            lambda: user_actions.set_user_unit(svc["unit"], on), done,
            lambda e: self._done("service", False, str(e)))

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
            self._run("service", [service_id, "on" if on else "off"],
                      on_success=lambda done: self._user_service(
                          svc, on, done))
            return
        self._run("service", [service_id, "on" if on else "off"])

    @Slot(bool)
    def setAutostart(self, enabled):
        autostart.set_enabled(enabled)
        self.refresh()

    @Slot(str)
    def launch(self, launcher_id):
        # A failed launch must not offer the earlier action again
        self._set_retry(None)
        super().launch(launcher_id)

    @Slot()
    def copySysinfo(self):
        QGuiApplication.clipboard().setText(self._state.get("sysinfo", ""))
