# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI side: helper runs and background work (needs PySide6)."""

import sys
import textwrap

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from nazoos_common import errors  # noqa: E402
from nazoos_common.qt import HelperProcess  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


def wait(app, done, timeout=10_000):
    timer = QtCore.QElapsedTimer()
    timer.start()
    while not done() and timer.elapsed() < timeout:
        app.processEvents(QtCore.QEventLoop.AllEvents, 50)
    assert done(), "timed out"


def run_fake(app, tmp_path, body, code, translate=lambda s: s, stdin=None):
    """Run a fake helper (python script) the way the GUI runs the real
    one, without pkexec. Returns (finished args, log, process)."""
    script = tmp_path / "helper"
    script.write_text("import sys\n" + textwrap.dedent(body)
                      + f"\nsys.exit({code})\n")
    proc = HelperProcess(str(script), translate,
                         launcher=(sys.executable,))
    result, log = [], []
    proc.finished.connect(lambda ok, msg: result.append((ok, msg)))
    proc.output.connect(log.append)
    proc.start(["action", 1], stdin)
    wait(app, lambda: result)
    return result[0], "".join(log), proc


def test_success(app, tmp_path):
    (ok, msg), log, proc = run_fake(app, tmp_path, """
        print("args", sys.argv[1:], sys.stdin.readline().strip())
        print("@@reboot")
    """, 0, stdin="secret")
    assert (ok, msg) == (True, "Done.")
    assert "args ['action', '1'] secret" in log
    assert proc.reboot


def test_error_line_is_translated(app, tmp_path):
    line = errors.encode("still failing: {units}", {"units": "a.service"})
    german = {"Something went wrong.": "Etwas ist schiefgegangen.",
              "still failing: {units}": "schlägt weiter fehl: {units}"}
    (ok, msg), _log, _p = run_fake(
        app, tmp_path, f"print({line!r})", 1,
        translate=lambda s: german.get(s, s))
    assert not ok
    assert msg == "Etwas ist schiefgegangen. schlägt weiter fehl: a.service"


def test_last_line_without_newline(app, tmp_path):
    line = errors.encode("unknown user")
    (ok, msg), _log, _p = run_fake(
        app, tmp_path, f"sys.stdout.write({line!r})", 1)
    assert msg == "Something went wrong. unknown user"


def test_pkexec_cancelled(app, tmp_path):
    (ok, msg), _log, _p = run_fake(app, tmp_path, "", 126)
    assert (ok, msg) == (False,
                         "Cancelled: no administrator password was given.")


def test_launcher_missing(app, tmp_path):
    proc = HelperProcess("x", lambda s: s,
                         launcher=(str(tmp_path / "no-pkexec"),))
    result = []
    proc.finished.connect(lambda ok, msg: result.append((ok, msg)))
    proc.start([])
    wait(app, lambda: result)
    assert result == [(False, "pkexec could not be started.")]


def test_background_failure_reaches_the_gui_thread(app, monkeypatch):
    from nazoos_welcome import backend, i18n

    b = backend.Backend(i18n.translator())
    seen = []

    def work():
        raise RuntimeError("probe broke")

    b._background(work, lambda r: seen.append(("done", r)),
                  lambda e: seen.append(("failed", str(e))))
    wait(app, lambda: seen)
    assert seen == [("failed", "probe broke")]


def test_refresh_survives_a_broken_probe(app, monkeypatch):
    from nazoos_welcome import backend, i18n

    def collect():
        raise OSError("no lspci")

    monkeypatch.setattr(backend.system, "collect", collect)
    b = backend.Backend(i18n.translator())
    b.refresh()
    wait(app, lambda: not b._refreshing)
    assert b.state.get("error") == "no lspci"
