# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI side: helper runs and background work (needs PySide6)."""

import os
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
    assert msg == "Etwas ist schiefgegangen. Schlägt weiter fehl: a.service"


def test_last_line_without_newline(app, tmp_path):
    line = errors.encode("unknown user")
    (ok, msg), _log, _p = run_fake(
        app, tmp_path, f"sys.stdout.write({line!r})", 1)
    assert msg == "Something went wrong. Unknown user"


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


def testbackground_failure_reaches_the_gui_thread(app, monkeypatch):
    from nazoos_welcome import backend, i18n

    b = backend.Backend(i18n.translator())
    seen = []

    def work():
        raise RuntimeError("probe broke")

    b.background(work, lambda r: seen.append(("done", r)),
                  lambda e: seen.append(("failed", str(e))))
    wait(app, lambda: seen)
    assert seen == [("failed", "probe broke")]


def test_refresh_survives_a_broken_probe(app, monkeypatch):
    from nazoos_welcome import backend, i18n

    def collect():
        raise OSError("no lspci")

    monkeypatch.setattr(backend.probes, "collect", collect)
    b = backend.Backend(i18n.translator())
    b.refresh()
    wait(app, lambda: not b._refreshing)
    assert b.state.get("error") == "no lspci"


def test_changed_card_is_read_before_the_full_refresh(app, monkeypatch):
    from nazoos_welcome import backend, i18n

    monkeypatch.setitem(backend.QUICK_PROBES, "channel",
                        ("channel", lambda: "beta"))
    monkeypatch.setattr(backend.probes, "collect",
                        lambda: {"channel": "beta", "fresh": True})
    b = backend.Backend(i18n.translator())
    b._state = {"channel": "stable"}
    b._refreshing = True  # a refresh from before the switch is running
    b._done("channel", True, "Done.")
    assert b.state["channel"] == "beta"
    # The old refresh lands late: it must not bring "stable" back
    b._set_state({"channel": "stable"})
    assert b.state["channel"] == "beta"
    wait(app, lambda: b.state.get("fresh"))
    assert not b._quick


@pytest.fixture
def welcome(app, tmp_path, monkeypatch):
    """A welcome Backend whose helper is a fake script run without pkexec.
    Returns (backend, finished results)."""
    from nazoos_common import qt
    from nazoos_welcome import backend, i18n

    script = tmp_path / "helper"
    script.write_text(
        "import sys\nprint('argv', sys.argv[1:])\n"
        "sys.exit(1 if sys.argv[1] == 'fails' else 0)\n")
    monkeypatch.setattr(backend, "HELPER", str(script))
    monkeypatch.setattr(
        qt, "HelperProcess",
        lambda helper, tr, parent: HelperProcess(
            helper, tr, parent, launcher=(sys.executable,)))
    monkeypatch.setitem(backend.catalog.ACTION_LABELS, "fails", "Failing")
    b = backend.Backend(i18n.translator())
    b.refresh = lambda: None
    seen = []
    b.actionFinished.connect(lambda *a: seen.append(a))
    return b, seen


def test_welcome_passes_the_action_to_the_helper(app, welcome):
    b, seen = welcome
    b.run("automount-remove", ["uuid-1"])
    wait(app, lambda: seen)
    assert "argv ['automount-remove', 'uuid-1']" in b._log


def test_retry_repeats_the_failed_action(app, welcome):
    b, seen = welcome
    assert not b.canRetry
    b.run("fails", ["x"])
    wait(app, lambda: seen)
    assert seen[-1][:2] == ("fails", False)
    assert b.canRetry
    b.retry()
    wait(app, lambda: len(seen) == 2)
    assert b._log.count("argv ['fails', 'x']") == 2


def test_retry_of_a_mok_action_asks_for_the_password_again(app, welcome):
    b, seen = welcome
    b.run("fails", ["x"], "hash")
    wait(app, lambda: seen)
    asked = []
    b.mokRetryRequested.connect(lambda a, args: asked.append((a, args)))
    b.retry()
    assert asked == [("fails", ["x"])]
    assert not b.busy


def test_failed_user_service_switch_offers_no_retry(app, welcome):
    b, seen = welcome
    b.run("fails", [])
    wait(app, lambda: seen)
    assert b.canRetry
    # The next task (a user unit, no helper run) replaces what was retried
    b._begin("service")
    b._done("service", False, "no")
    assert not b.canRetry
    b.retry()
    assert not b.busy


def test_second_start_hands_page_and_token_over(app, tmp_path, monkeypatch):
    from nazoos_common.single import TOKEN, Instance

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    first = Instance("nazoos-test")
    assert first.acquire()
    first.listen()
    pages = []
    first.pageRequested.connect(pages.append)

    second = Instance("nazoos-test")
    assert not second.acquire()
    monkeypatch.setenv(TOKEN, "launcher-token")
    assert second.send("rollback")
    monkeypatch.delenv(TOKEN)
    wait(app, lambda: pages)
    assert pages == ["rollback"]
    # Qt takes it from the environment on requestActivate()
    assert os.environ[TOKEN] == "launcher-token"
    monkeypatch.delenv(TOKEN)


def test_repair_model_rechecks_after_a_repair_action(app, monkeypatch):
    from nazoos_welcome import backend, i18n, repair, repair_model

    calls = []
    monkeypatch.setattr(repair, "check", lambda: calls.append(1) or [])
    b = backend.Backend(i18n.translator())
    model = repair_model.RepairModel(b)
    # Not checked yet: a repair action does not start a check
    b.actionFinished.emit("repair-rpmdb", True, "Done.")
    assert calls == []
    model.checkSystem()
    wait(app, lambda: model.checked)
    b.actionFinished.emit("kparam", True, "Done.")
    assert len(calls) == 1
    b.actionFinished.emit("repair-rpmdb", True, "Done.")
    wait(app, lambda: len(calls) == 2 and not model.checking)


def test_update_action_finishes_after_the_new_status_is_loaded(app, monkeypatch):
    from nazoos_update import backend, status

    conflict = {"error": status.ERROR_CONFLICT, "conflict": True}
    monkeypatch.setattr(status, "collect", lambda: {})
    b = backend.Backend()
    monkeypatch.setattr(status, "collect", lambda: conflict)
    seen = []
    b.actionFinished.connect(
        lambda action, ok, msg: seen.append(dict(b.state)))
    b._done("update", False, "failed")
    wait(app, lambda: seen)
    assert seen == [conflict]


def test_update_refresh_survives_a_broken_collect(app, monkeypatch):
    from nazoos_update import backend, status

    monkeypatch.setattr(status, "collect", lambda: {"a": 1})
    b = backend.Backend()

    def broken():
        raise OSError("gone")

    monkeypatch.setattr(status, "collect", broken)
    seen = []
    b.actionFinished.connect(lambda *a: seen.append(dict(b.state)))
    b._done("check", True, "Done.")
    wait(app, lambda: seen)
    assert seen == [{"a": 1}]
