# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""What the QML pages and the repair page expect from the Python side."""

import re
import subprocess
from pathlib import Path

import pytest

from nazoos_common import kernel, proc
from nazoos_welcome import appicons, probes
from nazoos_welcome.root import ACTIONS, STRICT_ACTIONS

WELCOME = Path(__file__).resolve().parent.parent / "packages/nazoos-welcome"
STATE_KEY = re.compile(r"\b(?:st|app\.st|page\.st|root\.st)\.([A-Za-z_]+)")
# Set by the backend itself, not by collect()
BACKEND_KEYS = {"error"}
PAGE_ARG = re.compile(
    r'nazoos-welcome"?(?:,\s*"|\s+)--page"?(?:,\s*"|\s+)([a-z]+)')


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
    monkeypatch.setattr(proc, "run", lambda cmd, timeout=30: (127, ""))
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
    missing = keys - BACKEND_KEYS - set(probes.collect())
    assert not missing


def test_every_repair_fix_is_a_root_action():
    text = (WELCOME / "nazoos_welcome/repair_checks.py").read_text()
    fixes = set(re.findall(r'"(repair-[a-z]+)"', text))
    assert fixes
    assert fixes <= set(ACTIONS) | set(STRICT_ACTIONS)


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
    assert ids <= set(ACTIONS) | set(STRICT_ACTIONS)


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
    assert {kernel.phase({**base, **c}) for c in cases} >= used


def test_kernel_page_stage2_values_are_produced_by_kernel():
    from nazoos_common import kernel

    page = (WELCOME / "qml/pages/KernelPage.qml").read_text()
    used = set(re.findall(r'k\.stage2 === "([a-z]+)"', page))
    assert used and used <= {"ready", "waiting"}
    made = {kernel.stage2_state(True, n, True, False) for n in (0, 99)}
    assert made == {"ready", "waiting"}


def test_every_page_other_programs_open_exists():
    """notify.py, nazoos-update and nazoos-session-select start
    "nazoos-welcome --page NAME"; an unknown NAME silently opens the
    welcome page (Main.qml showPage)."""
    pages = set(re.findall(r'\{ name: "([a-z]+)"',
                           (WELCOME / "qml/Main.qml").read_text()))
    found = set()
    for f in WELCOME.parent.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            found.update(PAGE_ARG.findall(
                f.read_text(errors="ignore")))
    assert {"kernel", "repair"} <= found
    assert found <= pages


def test_the_policy_has_own_actions_for_the_lasting_steps():
    import xml.etree.ElementTree as ET

    from nazoos_welcome import catalog
    from nazoos_welcome import root as root_actions

    strict_path = "/usr/libexec/nazoos-welcome/nazoos-welcome-helper-strict"
    tree = ET.parse(WELCOME / "data/org.nazoos.welcome.policy").getroot()
    strict, normal = {}, []
    for act in tree.iter("action"):
        notes = {n.get("key"): n.text for n in act.iter("annotate")}
        argv1 = notes.get("org.freedesktop.policykit.exec.argv1")
        if notes["org.freedesktop.policykit.exec.path"] == strict_path:
            assert argv1
            strict[argv1] = {d.tag: d.text for d in act.find("defaults")}
        else:
            normal.append(argv1)
    assert set(strict) == set(catalog.STRICT_ACTIONS) \
        == set(root_actions.STRICT_ACTIONS)
    for defaults in strict.values():
        assert defaults == dict.fromkeys(
            ("allow_any", "allow_inactive", "allow_active"), "auth_admin")
    # Only the catch-all is left on the normal path
    assert normal == [None]


def test_the_repair_page_reads_what_the_update_check_writes(monkeypatch,
                                                            tmp_path):
    import json

    from nazoos_update import status
    from nazoos_welcome import repair_checks

    assert repair_checks.UPDATE_STATUS == status.STATUS
    assert repair_checks.UPDATE_ERROR_KEY == status.ERROR_KEY
    fpr = "4AFF5EF3C350A53A05D6BA0D1E8EDBE858DDEB32"
    key = {"repo": "keytest", "label": "Some Name", "fingerprint": fpr,
           "shown": "Some Name: 4AFF 5EF3"}
    written = tmp_path / "status.json"
    written.write_text(json.dumps(
        status.new(error=status.ERROR_KEY, keys=[key])))
    monkeypatch.setattr(repair_checks, "UPDATE_STATUS", written)
    assert repair_checks.untrusted_keys() == [key]


def test_update_names_the_snapshots_welcome_takes():
    from nazoos_update.root import snapshots
    from nazoos_welcome import system
    from nazoos_welcome.root import maintenance

    def label(description):
        return snapshots.snapshot_label(
            {"number": 7, "type": "single", "description": description},
            set(), False, lambda s: s)

    assert label(maintenance.MANUAL_SNAPSHOT) == "Manual snapshot"
    for target in system.CHANNEL_REPO_PATHS:
        assert label(maintenance.CHANNEL_SNAPSHOT.format(target=target)
                     ) == "Before channel switch"
