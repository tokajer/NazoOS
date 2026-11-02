# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-greeter-restore against fake loginctl, systemctl, busctl, sleep."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).parent.parent
          / "packages/nazoos-session/libexec/nazoos-greeter-restore")

# FAKE_SESSIONS: file of "id:seat:Type:Class:VTNr" entries; the seat can be empty
LOGINCTL = """#!/bin/bash
if [ "$1" = list-sessions ]; then
  for e in $(cat "$FAKE_SESSIONS"); do echo "  ${e%%:*} 1000 user"; done
  exit 0
fi
IFS=: read -r id seat type cls vt <<< "$(grep "^$2:" "$FAKE_SESSIONS")"
case $4 in
  Seat) echo "$seat" ;; Type) echo "$type" ;; Class) echo "$cls" ;; VTNr) echo "$vt" ;;
esac
"""
SYSTEMCTL = """#!/bin/bash
echo "systemctl $*" >> "$FAKE_LOG"
if [ "$1" = is-active ]; then
  case $3 in
    display-manager.service) [ "${FAKE_DM-yes}" = yes ] ;;
    getty@*) [ -e "$FAKE_BUSY/$3" ] ;;
  esac
fi
"""
# The first sleep frees the VT, like the user leaving the text console
SLEEP = """#!/bin/bash
echo sleep >> "$FAKE_LOG"
rm -f "$FAKE_BUSY"/*
: > "$FAKE_SESSIONS"
"""


@pytest.fixture
def restore(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    busy = tmp_path / "busy"
    busy.mkdir()
    log = tmp_path / "log"
    log.touch()
    sess_file = tmp_path / "sessions"
    tty = tmp_path / "sys/class/tty/tty0"
    tty.mkdir(parents=True)
    (tty / "active").write_text("tty1\n")
    stubs = {
        "loginctl": LOGINCTL, "systemctl": SYSTEMCTL, "sleep": SLEEP,
        "busctl": '#!/bin/bash\necho "busctl $*" >> "$FAKE_LOG"\n',
        "id": '#!/bin/bash\n[ "$2" = sddm ] && echo 462 && exit 0\n'
              'exec /usr/bin/id "$@"\n',
    }
    for name, body in stubs.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)

    def run(*args, sessions="", dm="yes", getty_busy=None):
        sess_file.write_text(sessions.replace(" ", "\n"))
        if getty_busy:
            (busy / f"getty@{getty_busy}.service").touch()
        r = subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True,
            timeout=20,
            env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                 "NAZOOS_SESSION_ROOT": str(tmp_path), "FAKE_LOG": str(log),
                 "FAKE_BUSY": str(busy), "FAKE_SESSIONS": str(sess_file),
                 "FAKE_DM": dm})
        r.calls = log.read_text().splitlines()
        return r
    return run


def busctl_calls(r):
    return [c for c in r.calls if c.startswith("busctl")]


def test_trigger_ignores_other_users(restore):
    r = restore("trigger", "1000")
    assert r.returncode == 0
    assert r.calls == []


def test_trigger_starts_the_unit_for_sddm(restore):
    r = restore("trigger", "462")
    assert r.calls == ["systemctl --no-block start nazoos-greeter-restore.service"]


@pytest.mark.parametrize("sessions", [
    "c1:seat0:wayland:user:2",
    "c1:seat0:x11:user:2",
    "c2:seat0:wayland:greeter:1",
])
def test_wait_leaves_a_occupied_seat_alone(restore, sessions):
    r = restore("wait", sessions=sessions)
    assert r.returncode == 0
    assert busctl_calls(r) == []


def test_wait_ends_when_display_manager_is_stopped(restore):
    r = restore("wait", dm="no")
    assert r.returncode == 0
    assert busctl_calls(r) == []


def test_wait_ignores_wayland_session_on_another_seat(restore):
    r = restore("wait", sessions="c1:seat1:wayland:user:")
    assert len(busctl_calls(r)) == 1


def test_wait_keeps_waiting_while_a_text_console_is_in_use(restore):
    r = restore("wait", getty_busy="tty1")
    assert "sleep" in r.calls
    # The call comes only after the VT was freed
    assert r.calls.index("sleep") < r.calls.index(busctl_calls(r)[0])
    assert len(busctl_calls(r)) == 1


def test_wait_keeps_waiting_while_a_session_owns_the_vt(restore):
    # A tty session without getty unit state, but on the active VT
    r = restore("wait", sessions="t1:seat0:tty:user:1")
    assert "sleep" in r.calls
    assert len(busctl_calls(r)) == 1


def test_wait_calls_switch_to_greeter(restore):
    r = restore("wait", sessions="t1::tty:user:")
    assert busctl_calls(r) == [
        "busctl --system call org.freedesktop.DisplayManager "
        "/org/freedesktop/DisplayManager/Seat0 "
        "org.freedesktop.DisplayManager.Seat SwitchToGreeter"]
    assert "sleep" not in r.calls


def test_a_tty_session_elsewhere_does_not_block(restore):
    r = restore("wait", sessions="t2:seat0:tty:user:3")
    assert len(busctl_calls(r)) == 1
    assert "sleep" not in r.calls


def test_trigger_runs_as_root():
    # user@.service runs as the user: without "+" starting the unit is denied
    conf = (Path(__file__).parent.parent / "packages/nazoos-session/data"
            / "50-nazoos-greeter-restore.conf").read_text()
    assert ("ExecStopPost=-+/usr/libexec/nazoos-session/"
            "nazoos-greeter-restore trigger %i") in conf
