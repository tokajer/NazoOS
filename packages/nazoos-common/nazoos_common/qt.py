# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI side of the root helpers and small Qt helpers (needs PySide6)."""

import glob
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, Slot

from . import errors


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
        self._proc = None
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
        self._proc = proc
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
