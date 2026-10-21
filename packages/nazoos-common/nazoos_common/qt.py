# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI side of the root helpers and small Qt helpers (needs PySide6)."""

import glob
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from . import errors

# Works in the git tree and in /usr/share/nazoos-common
QML_DIR = str(Path(__file__).resolve().parent.parent / "qml")
# Characters kept in the log; trimmed to LOG_KEEP
LOG_MAX = 300_000
LOG_KEEP = 200_000
# Flatpak apps (LACT, CoolerControl) have their desktop files here
FLATPAK_EXPORTS = ["/var/lib/flatpak/exports/share"]


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

    def __init__(self, helper, gettext, parent=None, launcher=("pkexec",)):
        super().__init__(parent)
        self._helper = helper
        self._gettext = gettext
        self._launcher = list(launcher)
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
        cmd = self._launcher + [self._helper] + [str(a) for a in args]
        proc.start(cmd[0], cmd[1:])
        if stdin is not None:
            proc.write((stdin + "\n").encode())
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
        elif line == "@@reboot":
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


def desktop_file(patterns, extra_dirs=()):
    """First desktop file matching one of PATTERNS in the XDG dirs."""
    dirs = [Path.home() / ".local/share"] + [
        Path(d) for d in os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    dirs += [Path(d) for d in extra_dirs]
    for pattern in patterns:
        for d in dirs:
            hits = sorted(glob.glob(str(d / "applications" / pattern)))
            if hits:
                return hits[0]
    return None


def launch(patterns, fallback, extra_dirs=()):
    """Start an app by its desktop file (like the menu does), else by
    the FALLBACK command. False if neither is there."""
    desktop = desktop_file(patterns, extra_dirs) if patterns else None
    if desktop and shutil.which("kioclient"):
        cmd = ["kioclient", "exec", desktop]
    elif desktop and shutil.which("gio"):
        cmd = ["gio", "launch", desktop]
    elif fallback and shutil.which(fallback[0]):
        cmd = fallback
    else:
        return False
    subprocess.Popen(cmd, start_new_session=True)
    return True


# Apps the UI may start: desktop file patterns, then a fallback command
LAUNCHERS = {
    "discover": (["org.kde.discover.desktop"], ["plasma-discover"]),
    "updates": ([], ["plasma-discover", "--mode", "update"]),
    "nazoos-update": (["*nazoos-update*.desktop"], ["nazoos-update"]),
    "myrlyn": (["*myrlyn*sudo*.desktop", "*myrlyn*.desktop"], ["myrlyn"]),
    # btrfs-assistant itself needs root, the launcher asks for it
    "btrfs-assistant": (["*btrfs-assistant*.desktop"],
                        ["btrfs-assistant-launcher"]),
    "lact": (["*LACT*.desktop", "*lact*.desktop"], ["lact", "gui"]),
    "coolercontrol": (["*coolercontrol*.desktop"], ["coolercontrol"]),
    "steam": (["steam.desktop"], ["steam"]),
    "systemsettings": (["systemsettings.desktop"], ["systemsettings"]),
    "installer": (["nazoos-installer.desktop"], None),
    "repair": ([], ["nazoos-welcome", "--page", "repair"]),
    # Ends the desktop session (nazoos-session)
    "gaming-mode": ([], ["nazoos-session-select", "gaming"]),
}


class ActionRunner(QObject):
    """busy/task/log of one root helper run at a time; base class of the
    Backends of nazoos-welcome and nazoos-update."""

    busyChanged = Signal()
    logChanged = Signal()
    # action, success, message (already translated)
    actionFinished = Signal(str, bool, str)

    def __init__(self, helper, gettext, labels):
        """LABELS: {action: English label} of the actions that may run."""
        super().__init__()
        self._helper = helper
        self._gettext = gettext
        self._labels = labels
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

    def _helper_finished(self, action, proc, ok, message):
        """The run of ACTION ended; subclasses override. PROC.reboot is
        True after an "@@reboot" line."""
        raise NotImplementedError

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self._log)

    @Slot(str)
    def launch(self, launcher_id):
        entry = LAUNCHERS.get(launcher_id)
        if entry is None:
            return
        if not launch(*entry, extra_dirs=FLATPAK_EXPORTS):
            self.actionFinished.emit(
                "launch", False, self._gettext("This program is not installed."))
