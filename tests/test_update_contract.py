# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""What the update window's QML expects from the status."""

import re
from pathlib import Path

import pytest

from nazoos_common import proc
from nazoos_update import status

UPDATE = Path(__file__).resolve().parent.parent / "packages/nazoos-update"
STATE_KEY = re.compile(r"\b(?:st|root\.st)\.([A-Za-z_]+)")


def test_every_state_key_of_the_qml_pages_exists(monkeypatch):
    keys = set()
    for f in (UPDATE / "qml").rglob("*.qml"):
        keys.update(STATE_KEY.findall(f.read_text()))
    assert "packages" in keys   # the regex still finds something
    saved = status.new()
    saved.update(checked=1, last_ok=1, **dict.fromkeys(status.UPDATE_KEYS, 0))
    monkeypatch.setattr(status, "read_status", lambda: saved)
    monkeypatch.setattr(proc, "boot_time", lambda: 0)
    monkeypatch.setattr(proc, "out", lambda cmd, timeout=30: "")
    monkeypatch.setattr(proc, "is_live", lambda: False)
    assert not keys - set(status.collect())


def test_every_action_and_launcher_id_in_the_qml_exists():
    pytest.importorskip("PySide6")
    from nazoos_update import backend

    text = "\n".join(f.read_text() for f in (UPDATE / "qml").rglob("*.qml"))
    actions = set(re.findall(r'backend\.run\("([a-z]+)"', text))
    launchers = set(re.findall(r'backend\.launch\("([a-z0-9-]+)"', text))
    assert actions and launchers   # the regexes still find something
    assert actions <= set(backend.ACTION_LABELS)
    assert launchers <= set(backend.LAUNCHERS)
