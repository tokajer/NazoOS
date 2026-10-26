# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page state for QML: findings and the bug report (ADR 0012)."""

from nazoos_common.qt import CoalescedLoad
from PySide6.QtCore import Property, QObject, Signal, Slot

from . import repair_checks, report


class RepairModel(QObject):
    findingsChanged = Signal()
    # Path of a saved bug report
    reportSaved = Signal(str)

    def __init__(self, backend):
        super().__init__()
        self._backend = backend
        # None = not checked yet
        self._findings = None
        # A repair that ends during a check queues one more check, so the
        # findings never show the state from before the repair
        self._loader = CoalescedLoad(
            backend, repair_checks.check, self._set_findings, self._failed)
        self._reporting = False
        backend.actionFinished.connect(self._action_finished)

    def _get_findings(self):
        return self._findings if self._findings is not None else []

    findings = Property("QVariantList", _get_findings, notify=findingsChanged)

    def _get_checked(self):
        return self._findings is not None

    checked = Property(bool, _get_checked, notify=findingsChanged)

    def _get_checking(self):
        # pending is still set while the handler of the previous load runs
        return self._loader.running or self._loader.pending

    checking = Property(bool, _get_checking, notify=findingsChanged)

    def _action_finished(self, action, ok, message):
        if action.startswith("repair-") and self._findings is not None:
            self._loader.request()
            self.findingsChanged.emit()

    @Slot()
    def checkSystem(self):
        if self._get_checking():
            return
        self._loader.request()
        self.findingsChanged.emit()

    def _failed(self, e):  # a broken probe is a finding too
        self._set_findings([{"id": "error", "items": [str(e)],
                             "fix": "", "userFix": False, "args": []}])

    def _set_findings(self, found):
        self._findings = found
        self.findingsChanged.emit()

    @Slot()
    def saveReport(self):
        if self._reporting:
            return
        self._reporting = True
        backend = self._backend
        state, findings, log = backend.state, self._findings, backend.log

        def done(path):
            self._reporting = False
            self.reportSaved.emit(path)

        def failed(e):
            self._reporting = False
            backend.report_error("report", str(e))

        backend.background(
            lambda: report.report(state, findings, log), done, failed)
