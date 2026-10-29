# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Frame of the root helpers: exit codes and the last output line."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nazoos_common import errors, helper


@pytest.fixture
def root(monkeypatch):
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    # main() sets these for zypper; keep the test process clean
    monkeypatch.setenv("ZYPP_LOCK_TIMEOUT", "")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")


def last_error(capsys):
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith(errors.PREFIX)
    return json.loads(line[len(errors.PREFIX):])


def test_not_root(monkeypatch, capsys):
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1000)
    assert helper.main({"a": print}, 1, argv=["h", "a"]) == 1
    assert last_error(capsys)["msg"] == "must run as root (via pkexec)"


def test_unknown_action(root, capsys):
    assert helper.main({"a": print}, 1, argv=["h", "b"]) == 2
    assert last_error(capsys)["msg"] == "unknown action"


def test_the_normal_welcome_helper_refuses_the_strict_steps(root, capsys):
    from nazoos_welcome.root import ACTIONS

    assert helper.main(ACTIONS, 1, argv=["x", "repair-key", "a", "b"]) == 2
    assert last_error(capsys)["msg"] == "unknown action"


def test_too_many_arguments(root, capsys):
    assert helper.main({"a": print}, 1, max_args=0,
                       argv=["h", "a", "x"]) == 2


def test_success_gets_the_arguments(root, capsys):
    seen = []
    assert helper.main({"a": seen.append}, 1, argv=["h", "a", "x"]) == 0
    assert seen == [["x"]]


def test_fail_sends_template_and_values(root, capsys):
    def action(_args):
        raise helper.Fail("still failing: {units}", units="a, b")

    assert helper.main({"a": action}, 1, argv=["h", "a"]) == 1
    assert last_error(capsys) == {"msg": "still failing: {units}",
                                  "args": {"units": "a, b"}}


def test_os_error(root, capsys):
    def action(_args):
        raise FileNotFoundError(2, "No such file", "/x")

    assert helper.main({"a": action}, 1, argv=["h", "a"]) == 1
    err = last_error(capsys)
    assert err["msg"] == "system error: {detail}"
    assert "/x" in err["args"]["detail"]


def test_bug_still_reaches_the_user(root, capsys):
    def action(_args):
        return {}["missing"]

    assert helper.main({"a": action}, 1, argv=["h", "a"]) == 1
    err = last_error(capsys)
    assert err["msg"] == "program error: {detail}"
    assert err["args"]["detail"].startswith("KeyError")


def test_passthrough_ends_without_an_error_line(root, capsys):
    def action(_args):
        raise helper.Passthrough(7)

    assert helper.main({"a": action}, 1, argv=["h", "a"]) == 7
    assert errors.PREFIX not in capsys.readouterr().out


def test_fail_text_is_filled():
    assert str(helper.Fail("x {n}", n=2)) == "x 2"


class FakeProc:
    """subprocess.Popen stand-in for helper.run: exit code RC, output OUT."""

    def __init__(self, rc, out=b""):
        self.returncode = rc
        self.stdout = io.BytesIO(out)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_popen(monkeypatch, rc, out=b""):
    monkeypatch.setattr(helper.subprocess, "Popen",
                        lambda *a, **k: FakeProc(rc, out))


@pytest.mark.parametrize("rc, expected", [(0, 0), (102, 0), (106, 0)])
def test_run_zypper_notes_count_as_success(monkeypatch, capsys, rc,
                                           expected):
    fake_popen(monkeypatch, rc)
    assert helper.run(["zypper", "refresh"]) == expected


def test_run_failure(monkeypatch):
    fake_popen(monkeypatch, 4)
    with pytest.raises(helper.Fail) as e:
        helper.run(["zypper", "install", "x"])
    assert e.value.params == {"cmd": "zypper", "rc": 4}
    assert helper.run(["false"], check=False) == 4


def test_run_passes_the_output_on(monkeypatch, capsys):
    fake_popen(monkeypatch, 0, b"one\ntwo\n")
    seen = []
    helper.run(["zypper", "dup"], on_line=seen.append)
    assert seen == ["one\n", "two\n"]
    assert capsys.readouterr().out == "$ zypper dup\none\ntwo\n"


def test_say_takes_file_names_that_are_not_utf8(capsysbinary):
    # str(OSError) of such a name has lone surrogates; print() wrote them
    helper.say("/mnt/caf\udce9")
    assert capsysbinary.readouterr().out == b"/mnt/caf\xe9\n"


# A helper whose window is closed: its stdout pipe has no reader any more
GONE_READER = """
import sys
sys.path.insert(0, {common!r})
from nazoos_common import helper
helper.os.geteuid = lambda: 0

def act(_args):
    helper.run([sys.executable, "-c",
                "for i in range(200000): print('progress', i)"])
    helper.say("done")
    open({marker!r}, "w").write("finished")

sys.exit(helper.main({{"go": act}}, 1, argv=["helper", "go"]))
"""


def test_action_finishes_when_the_gui_goes_away(tmp_path):
    marker = tmp_path / "finished"
    common = Path(helper.__file__).resolve().parent.parent
    script = GONE_READER.format(common=str(common), marker=str(marker))
    with subprocess.Popen([sys.executable, "-c", script],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as proc:
        assert proc.stdout.readline().startswith(b"$ ")
        proc.stdout.close()     # the GUI is gone
        rc = proc.wait(timeout=60)
    # Before: the command died of SIGPIPE half-way and the action failed
    assert rc == 0
    assert marker.read_text() == "finished"


def test_arg():
    assert helper.arg(["on"], 0, ("on", "off")) == "on"
    with pytest.raises(helper.Fail, match="missing argument"):
        helper.arg([], 0)
    with pytest.raises(helper.Fail, match="invalid argument: maybe"):
        helper.arg(["maybe"], 0, ("on", "off"))


def test_fail_exit_code(root, capsys):
    class Quiet(helper.Fail):
        rc = 3

    def action(_args):
        raise Quiet("recorded")

    assert helper.main({"a": action}, 1, argv=["h", "a"]) == 3
    assert last_error(capsys)["msg"] == "recorded"
