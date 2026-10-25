# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""What the QML pages and the repair page expect from the Python side."""

import re
import subprocess
from pathlib import Path

import pytest

from nazoos_common import proc
from nazoos_welcome import appicons, probes, report
from nazoos_welcome.root import ACTIONS

WELCOME = Path(__file__).resolve().parent.parent / "packages/nazoos-welcome"
STATE_KEY = re.compile(r"\b(?:st|app\.st|page\.st|root\.st)\.([A-Za-z_]+)")
# Set by the backend itself, not by collect()
BACKEND_KEYS = {"error"}


def _qml_state_keys():
    keys = set()
    for f in (WELCOME / "qml").rglob("*.qml"):
        keys.update(STATE_KEY.findall(f.read_text()))
    return keys


@pytest.fixture
def silent_system(monkeypatch):
    """No command output, no file contents of the real system: every probe
    answers empty (directory listings in /sys, /etc/zypp are still read)."""
    monkeypatch.setattr(proc, "out", lambda cmd, timeout=30: "")
    monkeypatch.setattr(proc, "rc", lambda cmd, timeout=30: 1)
    monkeypatch.setattr(proc, "read", lambda path: "")
    monkeypatch.setattr(proc.shutil, "which", lambda name: None)

    def no_subprocess(*a, **k):
        raise OSError("no commands in this test")
    monkeypatch.setattr(subprocess, "run", no_subprocess)
    monkeypatch.setattr(probes, "_deck_found", False)
    # A download thread started here would run after the patches are undone
    monkeypatch.setattr(appicons, "fetch_flathub", lambda *a, **k: None)


def test_every_state_key_of_the_qml_pages_exists(silent_system):
    keys = _qml_state_keys()
    assert "gpus" in keys   # the regex still finds something
    missing = keys - BACKEND_KEYS - set(report.collect_state())
    assert not missing


def test_every_repair_fix_is_a_root_action():
    text = (WELCOME / "nazoos_welcome/repair_checks.py").read_text()
    fixes = set(re.findall(r'"(repair-[a-z]+)"', text))
    assert fixes
    assert fixes <= set(ACTIONS)


def test_every_repair_finding_has_a_text():
    code = (WELCOME / "nazoos_welcome/repair_checks.py").read_text()
    # "error" is made by RepairModel when the check itself breaks
    ids = set(re.findall(r'_finding\("([a-z]+)"', code)) | {"error"}
    assert len(ids) > 2
    page = (WELCOME / "qml/pages/RepairPage.qml").read_text()
    # RepairPage.qml keys its texts as unquoted object keys: `rpmdb: {`;
    # a finding without an entry would render without title and button
    missing = {i for i in ids if not re.search(rf"\b{i}:\s*\{{", page)}
    assert not missing


def test_every_page_file_in_main_qml_exists():
    main = (WELCOME / "qml/Main.qml").read_text()
    files = re.findall(r'file: "([^"]+\.qml)"', main)
    assert files
    for f in files:
        assert (WELCOME / "qml/pages" / f).is_file(), f


def _qml_text():
    return "\n".join(f.read_text() for f in (WELCOME / "qml").rglob("*.qml"))


def _ids(text, fn):
    """Literal ids of fn("id", ...) and fn(cond ? "a" : "b", ...) calls."""
    ids = set(re.findall(rf'{fn}\("([a-z0-9-]+)"', text))
    for pair in re.findall(
            rf'{fn}\([^,\[)]*\?\s*"([a-z0-9-]+)"\s*:\s*"([a-z0-9-]+)"', text):
        ids.update(pair)
    return ids


def test_every_action_id_in_the_qml_is_a_root_action():
    ids = _ids(_qml_text(), "runAction") | _ids(_qml_text(), "askMok")
    assert len(ids) > 5   # the regex still finds something
    assert ids <= set(ACTIONS)


def test_every_launcher_id_in_the_qml_exists():
    pytest.importorskip("PySide6")
    from nazoos_welcome import backend

    ids = _ids(_qml_text(), r"backend\.launch")
    assert ids
    assert ids <= set(backend.LAUNCHERS)


def test_kernel_page_phases_are_produced_by_the_probe():
    page = (WELCOME / "qml/pages/KernelPage.qml").read_text()
    used = set(re.findall(r'k\.phase === "([a-z-]+)"', page))
    assert used == {"blocked", "running", "key-missing", "key-pending",
                    "not-preferred", "installed"}
    base = dict(blocked=False, running=False, installed=True,
                secureBoot=False, mok="", preferred=True)
    cases = [
        dict(blocked=True), dict(running=True),
        dict(secureBoot=True, mok="missing"),
        dict(secureBoot=True, mok="pending"),
        dict(preferred=False), {},
    ]
    assert {probes.kernel_phase({**base, **c}) for c in cases} >= used


def test_kernel_page_stage2_values_are_produced_by_kernel():
    from nazoos_common import kernel

    page = (WELCOME / "qml/pages/KernelPage.qml").read_text()
    used = set(re.findall(r'k\.stage2 === "([a-z]+)"', page))
    assert used and used <= {"ready", "waiting"}
    made = {kernel.stage2_state(True, n, True, False) for n in (0, 99)}
    assert made == {"ready", "waiting"}
