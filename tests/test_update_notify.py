# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notifications of nazoos-update --notify: which ones, and sending."""

import subprocess
import time

import pytest

from nazoos_update import notify, status

NOW = 1_000_000_000


def state(**kw):
    st = {"snapshot": "", "packages": [], "flatpaks": [], "count": 0,
          "needs_reboot": False, "error": "", "checked": NOW, "updated": 5,
          "last_ok": NOW}
    st.update(kw)
    return st


def keys(st, stable=False, welcome=False):
    return [i["key"] for i in notify.pending(st, NOW, stable, welcome)]


def test_snapshot_suppresses_everything_else():
    st = state(snapshot="42", count=3, needs_reboot=True, error="x")
    assert keys(st, True, True) == ["snapshot-42"]
    item = notify.pending(st, NOW, True, True)[0]
    assert item["urgency"] == "critical" and item["page"] == "rollback"


def test_reboot_key_uses_updated():
    assert keys(state(needs_reboot=True, updated=77)) == ["reboot-77"]


def test_kernel_stable_needs_both_flags():
    assert keys(state(), True, False) == []
    assert keys(state(), False, True) == []
    item = notify.pending(state(), NOW, True, True)[0]
    assert item["key"] == "kernel-stable"
    assert item["command"] == ["nazoos-welcome", "--page", "kernel"]
    assert item["remind"] == 7 * 24 * 3600


def test_conflict_suppresses_updates():
    st = state(count=2, error=status.ERROR_CONFLICT)
    assert keys(st) == [f"conflict-{NOW // notify.REMIND}"]


def test_updates_item():
    items = notify.pending(state(count=2), NOW, False, False)
    assert [i["key"] for i in items] == [
        f"updates-{notify._fingerprint(state())}"]


def test_error_only_after_grace():
    inside = state(error="offline", last_ok=NOW - notify.CHECK_GRACE)
    assert keys(inside) == []
    after = state(error="offline", last_ok=NOW - notify.CHECK_GRACE - 1)
    assert keys(after) == [f"error-{NOW // notify.REMIND}"]


@pytest.fixture
def sent(monkeypatch, tmp_path):
    monkeypatch.setattr(notify, "STATE", tmp_path)
    found = {"notify-send": True}
    monkeypatch.setattr(notify.shutil, "which",
                        lambda name: "/usr/bin/" + name
                        if found.get(name) else None)
    calls = []
    rc = {"systemd-run": 0}

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, rc.get(cmd[0], 0), stdout="", stderr="")

    monkeypatch.setattr(notify.subprocess, "run", run)
    return found, rc, calls


ITEM = notify._item("updates-abc", "t", "b", "a", "update")


def test_send_without_notify_send_saves_nothing(sent):
    found, _rc, calls = sent
    found["notify-send"] = False
    notify._send(ITEM)
    assert calls == [] and notify._load() == {}


def test_send_starts_own_unit_and_marks_seen(sent):
    _found, _rc, calls = sent
    notify._send(ITEM)
    assert "--unit=nazoos-update-notice-updates-abc.service" in calls[0]
    assert "--notify-one" in calls[0] and "updates-abc" in calls[0]
    assert "PartOf=graphical-session.target" in calls[0]
    assert "Requisite=graphical-session.target" in calls[0]
    assert "updates-abc" in notify._load()
    # Seen within its remind time: not started again
    notify._send(ITEM)
    assert len(calls) == 1


def test_send_failed_start_is_not_marked(sent):
    _found, rc, _calls = sent
    rc["systemd-run"] = 1
    notify._send(ITEM)
    assert notify._load() == {}


def test_save_drops_old_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(notify, "STATE", tmp_path)
    now = int(time.time())
    notify._save({"old": now - 9 * 24 * 3600, "new": now - 3600})
    assert list(notify._load()) == ["new"]


def test_show_launches_on_open(monkeypatch):
    launched = []
    monkeypatch.setattr(notify, "_launch", launched.append)
    monkeypatch.setattr(
        notify.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "open\n", ""))
    notify._show(ITEM)
    assert launched == [["nazoos-update", "--page", "update"]]


def test_notify_one_ignores_a_gone_notification(monkeypatch):
    shown = []
    monkeypatch.setattr(notify, "_show", shown.append)
    monkeypatch.setattr(notify, "_pending_now", lambda: [ITEM])
    assert notify.notify_one("other") == 0 and shown == []
    assert notify.notify_one("updates-abc") == 0 and shown == [ITEM]
