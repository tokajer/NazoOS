# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page state for QML: findings and the bug report (ADR 0012)."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import repair


class RepairModel(QObject):
    findingsChanged = Signal()
    # Path of a saved bug report
    reportSaved = Signal(str)

    def __init__(self, backend):
        super().__init__()
        self._backend = backend
        # None = not checked yet
        self._findings = None
        self._checking = False
        self._reporting = False
        backend.actionFinished.connect(self._action_finished)

    def _get_findings(self):
        return self._findings if self._findings is not None else []

    findings = Property("QVariantList", _get_findings, notify=findingsChanged)

    def _get_checked(self):
        return self._findings is not None

    checked = Property(bool, _get_checked, notify=findingsChanged)

    def _get_checking(self):
        return self._checking

    checking = Property(bool, _get_checking, notify=findingsChanged)

    def _action_finished(self, action, ok, message):
        if action.startswith("repair-") and self._findings is not None:
            self.checkSystem()

    @Slot()
    def checkSystem(self):
        if self._checking:
            return
        self._checking = True
        self.findingsChanged.emit()

        def failed(e):  # a broken probe is a finding too
            self._set_findings([{"id": "error", "items": [str(e)],
                                 "fix": "", "userOnly": False}])

        self._backend.background(repair.check, self._set_findings, failed)

    def _set_findings(self, found):
        self._checking = False
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
            lambda: repair.report(state, findings, log), done, failed)
