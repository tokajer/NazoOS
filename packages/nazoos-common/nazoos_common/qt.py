# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI side of the root helpers and small Qt helpers (needs PySide6)."""

import os
import signal
import sys
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import (Property, QObject, QProcess, QTimer, QUrl, Signal,
                            Slot)
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from . import errors, launcher

# Works in the git tree and in /usr/share/nazoos-common
QML_DIR = str(Path(__file__).resolve().parent.parent / "qml")
# Characters kept in the log; trimmed to LOG_KEEP
LOG_MAX = 300_000
LOG_KEEP = 200_000


def find_qml(package_file, name):
    """Main.qml next to the git checkout or in /usr/share/NAME/qml."""
    for d in (Path(package_file).resolve().parent.parent / "qml",
              Path("/usr/share") / name / "qml"):
        if (d / "Main.qml").is_file():
            return d / "Main.qml"
    sys.exit(f"{name}: Main.qml not found")


def application(name, display_name, desktop_id, icons, version, qt_args):
    """QApplication with the native Plasma style unless the user chose one.
    ICONS: theme icon names, the first that exists is the window icon."""
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")
    # QApplication (not QGuiApplication): the desktop style needs widgets
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName(name)
    app.setApplicationDisplayName(display_name)
    app.setApplicationVersion(version)
    app.setOrganizationDomain("nazoos.org")
    QGuiApplication.setDesktopFileName(desktop_id)
    icon = QIcon()
    for n in reversed(icons):
        icon = QIcon.fromTheme(n, icon)
    app.setWindowIcon(icon)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app


def run_qml(package_file, name, instance, context):
    """Load NAME's Main.qml with the CONTEXT properties (and the single
    instance as "instance"), run the event loop, return its exit code."""
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    for key, value in context.items():
        ctx.setContextProperty(key, value)
    ctx.setContextProperty("instance", instance)
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(str(find_qml(package_file, name))))
    if not engine.rootObjects():
        return 1
    instance.listen()
    rc = QApplication.instance().exec()
    # The engine must go before the translator: QML bindings still call
    # L.tr() while it is torn down ("Cannot call method 'tr' of null")
    del engine
    return rc


class Translator(QObject):
    """gettext for Python and QML (L.tr, L.trn) of one translation."""

    def __init__(self, translation):
        super().__init__()
        self._t = translation

    def gettext(self, text):
        return self._t.gettext(text)

    def ngettext(self, singular, plural, n):
        return self._t.ngettext(singular, plural, n)

    @Slot(str, result=str)
    def tr(self, text):
        return self._t.gettext(text)

    @Slot(str, str, int, result=str)
    def trn(self, singular, plural, n):
        return self._t.ngettext(singular, plural, n).replace("%1", str(n))


class HelperProcess(QObject):
    """One run of a root helper via pkexec.

    output(text): helper output for the log. finished(ok, message):
    MESSAGE is translated, with the helper's "@@error" reason on failure.
    reboot is True after an "@@reboot" line.
    """

    output = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, helper, gettext, parent=None, launch_cmd=("pkexec",)):
        super().__init__(parent)
        self._helper = helper
        self._gettext = gettext
        self._launch_cmd = list(launch_cmd)
        self._partial = ""
        self._error = ""
        self.reboot = False

    def start(self, args, stdin=None):
        self._partial, self._error, self.reboot = "", "", False
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._read(proc))
        proc.finished.connect(lambda code, _s: self._finished(code))
        proc.errorOccurred.connect(self._failed_start)
        cmd = self._launch_cmd + [self._helper] + [str(a) for a in args]
        proc.start(cmd[0], cmd[1:])
        if stdin is not None:
            proc.write((stdin + "\n").encode())
        # A helper that reads stdin must see EOF, not wait for the GUI
        proc.closeWriteChannel()

    def _read(self, proc):
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
        # Output arrives in chunks: only whole lines carry "@@" markers
        lines = (self._partial + text).split("\n")
        self._partial = lines.pop()
        for line in lines:
            self._marker(line)
        self.output.emit(text)

    def _marker(self, line):
        if line.startswith(errors.PREFIX):
            self._error = errors.message(line[len(errors.PREFIX):],
                                         self._gettext)
        elif line == errors.REBOOT:
            self.reboot = True

    def _failed_start(self, err):
        if err == QProcess.FailedToStart:
            _ = self._gettext
            self.finished.emit(False, _("pkexec could not be started."))

    def _finished(self, code):
        _ = self._gettext
        if self._partial:
            self._marker(self._partial)
            self._partial = ""
        if code == 0:
            self.finished.emit(True, _("Done."))
        elif code in (126, 127) and not self._error:
            # pkexec: dialog dismissed or not authorized
            self.finished.emit(
                False, _("Cancelled: no administrator password was given."))
        else:
            msg = _("Something went wrong.")
            # Templates start lower case; here they follow a full stop
            reason = self._error[:1].upper() + self._error[1:]
            self.finished.emit(False, f"{msg} {reason}".strip())


class ActionRunner(QObject):
    """busy/task/log of one root helper run at a time; base class of the
    Backends of nazoos-welcome and nazoos-update."""

    busyChanged = Signal()
    logChanged = Signal()
    # action, success, message (already translated)
    actionFinished = Signal(str, bool, str)
    # Runs a callable on the GUI thread (see background)
    _call = Signal(object)

    def __init__(self, helper, gettext, labels, launchers):
        """LABELS: {action: English label} of the actions that may run.
        LAUNCHERS: {id: (desktop file patterns, fallback command)}."""
        super().__init__()
        self._helper = helper
        self._gettext = gettext
        self._labels = labels
        self._launchers = launchers
        self._call.connect(lambda f: f())
        self._busy = False
        self._task = ""
        self._log = ""
        # Every zypper output chunk would otherwise make QML re-set and
        # re-wrap up to 300 KB of text
        self._log_timer = QTimer(self)
        self._log_timer.setSingleShot(True)
        self._log_timer.setInterval(150)
        self._log_timer.timeout.connect(self.logChanged.emit)

    def _get_busy(self):
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_task(self):
        return self._task

    task = Property(str, _get_task, notify=busyChanged)

    def _get_log(self):
        return self._log

    log = Property(str, _get_log, notify=logChanged)

    def background(self, work, done, failed):
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

    def _append(self, text):
        self._log += text
        if len(self._log) > LOG_MAX:
            self._log = self._log[-LOG_KEEP:]
        if not self._log_timer.isActive():
            self._log_timer.start()

    def _begin(self, action):
        self._task = self._gettext(self._labels[action])
        self._busy = True
        self.busyChanged.emit()
        self._append(f"\n=== {self._task} ===\n")

    def _end_busy(self):
        self._busy = False
        self._task = ""
        self.busyChanged.emit()

    def _start(self, action, args, stdin=None):
        proc = HelperProcess(self._helper, self._gettext, self)
        proc.output.connect(self._append)

        def finished(ok, message):
            self._helper_finished(action, proc, ok, message)
            proc.deleteLater()

        proc.finished.connect(finished)
        proc.start([action, *args], stdin)

    def _helper_finished(self, action, helper_proc, ok, message):
        """The run of ACTION ended; subclasses override. HELPER_PROC.reboot is
        True after an "@@reboot" line."""
        raise NotImplementedError

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)

    @Slot(str)
    def launch(self, launcher_id):
        entry = self._launchers.get(launcher_id)
        if entry is None:
            return
        if not launcher.launch(*entry):
            self.actionFinished.emit(
                "launch", False, self._gettext("This program is not installed."))


class CoalescedLoad:
    """One background load at a time: a request during a load runs one
    more load after it. AFTER callbacks run once a load that started after
    their request has finished."""

    def __init__(self, runner, work, done, failed):
        """RUNNER: the ActionRunner whose background() runs WORK. DONE(result)
        or FAILED(exception) run on the GUI thread before the callbacks."""
        self._runner = runner
        self._work = work
        self._done = done
        self._failed = failed
        # A load is in flight / another one is queued after it
        self.running = False
        self.pending = False
        # Callbacks for the next load that starts
        self._after = []

    def request(self, after=None):
        if after:
            self._after.append(after)
        if self.running:
            self.pending = True
        else:
            self._start()

    def _start(self):
        self.running = True
        self.pending = False
        callbacks, self._after = self._after, []
        self._runner.background(
            self._work, lambda r: self._finish(callbacks, self._done, r),
            lambda e: self._finish(callbacks, self._failed, e))

    def _finish(self, callbacks, handler, value):
        self.running = False
        try:
            try:
                handler(value)
            finally:
                for callback in callbacks:
                    callback()
        finally:
            if self.pending:
                self._start()
