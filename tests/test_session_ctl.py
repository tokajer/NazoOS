# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-session-ctl against a fake root (NAZOOS_SESSION_ROOT)."""

import getpass
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).parent.parent
          / "packages/nazoos-session/libexec/nazoos-session-ctl")
USER = getpass.getuser()

# The script checks the user with getent and a name pattern
if shutil.which("getent") is None or not re.fullmatch(r"[a-z_][a-z0-9_.-]*", USER):
    pytest.skip("needs getent and a plain user name", allow_module_level=True)


@pytest.fixture
def root(tmp_path):
    sessions = tmp_path / "usr/share/wayland-sessions"
    sessions.mkdir(parents=True)
    (sessions / "plasmawayland.desktop").touch()
    dm = tmp_path / "etc/sysconfig/displaymanager"
    dm.parent.mkdir(parents=True)
    dm.write_text('DISPLAYMANAGER_AUTOLOGIN=""\n')
    # Owned by nazoos-session (%dir), the script expects it
    (tmp_path / "etc/nazoos").mkdir()
    return tmp_path


def ctl(root, *args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True,
        env={**os.environ, "NAZOOS_SESSION_ROOT": str(root)})


def session(root):
    f = root / "etc/sddm.conf.d/zz-nazoos-session.conf"
    m = re.search(r"^Session=(.*)$", f.read_text(), re.M) if f.exists() else None
    return m.group(1) if m else None


def autologin(root):
    text = (root / "etc/sysconfig/displaymanager").read_text()
    return re.search(r'^DISPLAYMANAGER_AUTOLOGIN="(.*)"$', text, re.M).group(1)


GAMING = "gamescope-session-steam.desktop"
DESKTOP = "plasmawayland.desktop"


def test_boot_mode_gaming_returns_after_a_desktop_session(root):
    assert ctl(root, "boot-mode", "gaming", USER).returncode == 0
    conf = (root / "etc/nazoos/session.conf").read_text()
    assert 'BOOT_MODE="gaming"' in conf
    assert session(root) == GAMING and autologin(root) == USER
    assert ctl(root, "switch", "desktop", USER).returncode == 0
    assert session(root) == DESKTOP
    assert ctl(root, "started", "desktop", USER).returncode == 0
    assert session(root) == GAMING
    assert ctl(root, "boot").returncode == 0
    assert session(root) == GAMING


def test_one_time_switch_does_not_survive_a_boot(root):
    oneshot = root / "etc/nazoos/session-oneshot"
    assert ctl(root, "switch", "gaming", USER).returncode == 0
    assert oneshot.read_text() == 'PREVIOUS=""\n'
    assert session(root) == GAMING and autologin(root) == USER
    ctl(root, "boot")
    assert not oneshot.exists()
    assert session(root) is None and autologin(root) == ""


def test_failed_gaming_mode_logs_into_the_desktop_once(root):
    oneshot = root / "etc/nazoos/session-oneshot"
    assert ctl(root, "failed", "gaming", USER).returncode == 0
    assert session(root) == DESKTOP and oneshot.exists()
    ctl(root, "started", "desktop", USER)
    assert not oneshot.exists()
    assert autologin(root) == ""


def test_invalid_user_writes_nothing(root):
    r = ctl(root, "boot-mode", "gaming", "no such user")
    assert r.returncode == 1
    assert not any((root / "etc/nazoos").iterdir())
    assert session(root) is None and autologin(root) == ""


def test_unknown_user_writes_nothing(root):
    r = ctl(root, "boot-mode", "gaming", "nazoos-nouser")
    assert r.returncode == 1
    assert not any((root / "etc/nazoos").iterdir())
    assert session(root) is None and autologin(root) == ""
