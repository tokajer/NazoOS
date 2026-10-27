# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between the QML pages and the system."""

import os
import sys
import time

from nazoos_common import mok
from nazoos_common.launcher import COMMON_LAUNCHERS
from nazoos_common.qt import ActionRunner, CoalescedLoad
from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from . import autostart, catalog, hw, probes, user_actions

# Cheap probes for the card an action changed: read right after it, the
# full probes.collect() takes 15-20 s (zypper searches).
# action: (state key, probe function)
QUICK_PROBES = {
    "channel": ("channel", probes.update_channel),
    "session-boot-mode": ("session", probes.session_state),
    "automount-add": ("drives", hw.drives),
    "automount-remove": ("drives", hw.drives),
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

# A page change re-reads the state only if it is older than this (s)
STALE_SECONDS = 30

HELPER = os.environ.get("NAZOOS_WELCOME_HELPER",
                        "/usr/libexec/nazoos-welcome/nazoos-welcome-helper")
STRICT_HELPER = os.environ.get(
    "NAZOOS_WELCOME_HELPER_STRICT",
    "/usr/libexec/nazoos-welcome/nazoos-welcome-helper-strict")


class Backend(ActionRunner):
    stateChanged = Signal()
    canRetryChanged = Signal()
    # Retry of a failed action that needs the MokManager password again
    mokRetryRequested = Signal(str, "QVariantList")

    def __init__(self, translator):
        super().__init__(HELPER, translator.gettext, catalog.ACTION_LABELS,
                         LAUNCHERS)
        self._state = {}
        # time.monotonic() of the last successful load
        self._loaded_at = float("-inf")
        # (action, args, needs MokManager password) of the last run() that
        # "Try again" may repeat, None after anything else
        self._retry = None
        self._on_finish = None
        # Never kill the UI over a probe
        self._loader = CoalescedLoad(
            self, probes.collect, self._loaded,
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

    @Slot()
    def refreshStale(self):
        """refresh() unless a load is running or the state is fresh;
        actions still refresh in full (_done)."""
        if (self._loader.running
                or time.monotonic() - self._loaded_at < STALE_SECONDS):
            return
        self.refresh()

    def _quick_refresh(self, action):
        key, probe = QUICK_PROBES[action]

        def apply(value):
            if self._state.get(key) != value:
                self._quick.add(key)
                self._state = dict(self._state, **{key: value})
                self.stateChanged.emit()
            self.refresh()

        # Probes start lsblk / nazoos-session-ctl: not on the GUI thread. The
        # full refresh follows the quick value, so a late quick result never
        # lands on top of a newer full load
        self.background(probe, apply, lambda _e: self.refresh())

    def _loaded(self, st):
        self._loaded_at = time.monotonic()
        self._set_state(st)

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
            # "Try again" repeats the system half
            self._start_helper(
                "repair-units", [], None,
                lambda ok, message: self._units_done(ok, message, still),
                retry=True)
        else:
            self._units_done(True, self._gettext("Done."), still)

    def _units_done(self, ok, message, still):
        """Finish fixUnits; user units that still fail make it a failure
        and are named next to the helper's system units."""
        if still:
            user = self._gettext(
                "These services still fail after a restart: %1").replace(
                    "%1", ", ".join(still))
            message = f"{message}\n{user}" if not ok and message else user
            ok = False
        self._done("repair-units", ok, message)

    # --- root actions ---------------------------------------------------------

    def _begin(self, action):
        self._set_retry(None)
        super()._begin(action)

    @Slot(str, "QVariantList")
    def run(self, action, args):
        self._run(action, args)

    def _run(self, action, args, stdin=None, on_finish=None, retry=True):
        """ON_FINISH(ok, message), if given, runs instead of _done() when
        the helper ends and must finish the task with _done(). RETRY: "Try
        again" may repeat this run."""
        if self._busy:
            return
        if action not in catalog.ACTION_LABELS:
            # A programming error in QML: leave a trace in the journal
            print(f"nazoos-welcome: unknown action {action}", file=sys.stderr)
            return
        self._begin(action)
        self._start_helper(action, args, stdin, on_finish, retry)

    def _start_helper(self, action, args, stdin, on_finish, retry):
        # stdin only carries the MokManager password hash (runMok)
        self._set_retry((action, list(args), stdin is not None)
                        if retry else None)
        self._on_finish = on_finish
        self._start(action, args, stdin,
                    helper=STRICT_HELPER if action in catalog.STRICT_ACTIONS
                    else None)

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

    def _helper_finished(self, action, helper_proc, ok, message):
        on_finish, self._on_finish = self._on_finish, None
        if on_finish:
            on_finish(ok, message)
        else:
            self._done(action, ok, message)

    def _done(self, action, ok, message):
        self._end_busy()
        self.actionFinished.emit(action, ok, message)
        if action in QUICK_PROBES:
            self._quick_refresh(action)
        else:
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
        needs_root_install = on and not installed
        if svc["user"] and not needs_root_install:
            self._begin("service")
            self._user_service(svc, on, lambda: self._done(
                "service", True, self._gettext("Done.")))
        elif svc["user"]:
            def finish(ok, message):
                if ok:
                    self._user_service(svc, on, lambda: self._done(
                        "service", True, message))
                    return
                self._done("service", False, message)

            self._run("service", [service_id, "on"], on_finish=finish,
                      retry=False)
        else:
            self._run("service", [service_id, "on" if on else "off"])

    @Slot(bool)
    def setAutostart(self, enabled):
        try:
            autostart.set_enabled(enabled)
        except OSError as e:
            self.report_error("autostart", self._gettext(
                "The autostart setting could not be changed: %1")
                .replace("%1", str(e)))
        self.refresh()

    @Slot(str)
    def launch(self, launcher_id):
        # A failed launch must not offer the earlier action again
        self._set_retry(None)
        super().launch(launcher_id)

    @Slot()
    def copySysinfo(self):
        QGuiApplication.clipboard().setText(self._state.get("sysinfo", ""))
