# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-session-switch against a fake loginctl."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).parent.parent
          / "packages/nazoos-session/libexec/nazoos-session-switch")
MESSAGE = "only the user in front"

# The script looks the user up with getent and execs the installed ctl
if shutil.which("getent") is None or Path(
        "/usr/libexec/nazoos-session/nazoos-session-ctl").exists():
    pytest.skip("needs getent and no installed nazoos-session-ctl",
                allow_module_level=True)

LOGINCTL = """#!/bin/bash
case "$1 $4" in
  "show-user Sessions") echo c1 ;;
  "show-session Seat") echo seat0 ;;
  "show-session User")
    if [ "$2" = c1 ]; then echo "$REAL_UID"; else echo 4242; fi ;;
  "show-session Class") echo "${FAKE_CLASS-user}" ;;
  "show-seat ActiveSession") echo "$FAKE_ACTIVE" ;;
esac
"""


@pytest.fixture
def switch(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # id: the root check passes
    for name, body in (("id", "#!/bin/bash\necho 0\n"),
                       ("loginctl", LOGINCTL)):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)

    def run(active, *args, cls="user"):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True,
            env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                 "PKEXEC_UID": str(os.getuid()),
                 "REAL_UID": str(os.getuid()), "FAKE_ACTIVE": active, "FAKE_CLASS": cls})
    return run


def test_switch_refuses_a_background_session(switch):
    r = switch("o1", "switch", "desktop")
    assert r.returncode == 1
    assert MESSAGE in r.stderr


def test_switch_allows_the_active_session(switch):
    # Reached the exec of the missing ctl (bash: 127, names the path)
    r = switch("c1", "switch", "desktop")
    assert r.returncode == 127
    assert "nazoos-session-ctl" in r.stderr


def test_switch_refuses_without_an_active_session(switch):
    r = switch("", "switch", "desktop")
    assert r.returncode == 1
    assert MESSAGE in r.stderr


def test_started_works_from_a_background_session(switch):
    r = switch("o1", "started", "gaming")
    assert r.returncode == 127
    assert "nazoos-session-ctl" in r.stderr


def test_failed_refuses_a_background_session(switch):
    r = switch("o1", "failed", "gaming")
    assert r.returncode == 1
    assert MESSAGE in r.stderr


def test_failed_works_while_the_greeter_is_in_front(switch):
    r = switch("o1", "failed", "gaming", cls="greeter")
    assert r.returncode == 127
    assert "nazoos-session-ctl" in r.stderr


def test_failed_works_without_an_active_session(switch):
    r = switch("", "failed", "gaming")
    assert r.returncode == 127
    assert "nazoos-session-ctl" in r.stderr


def test_failed_works_from_the_active_session(switch):
    r = switch("c1", "failed", "gaming")
    assert r.returncode == 127
    assert "nazoos-session-ctl" in r.stderr


def test_switch_refuses_while_the_greeter_is_in_front(switch):
    r = switch("o1", "switch", "desktop", cls="greeter")
    assert r.returncode == 1
    assert MESSAGE in r.stderr


def test_failed_refuses_an_unknown_session_class(switch):
    r = switch("o1", "failed", "gaming", cls="")
    assert r.returncode == 1
    assert MESSAGE in r.stderr
