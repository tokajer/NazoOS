# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-update: zypper XML, mirror check, snapshot names."""

import subprocess

import pytest

from nazoos_common.helper import Fail
from nazoos_update import status as status_mod
from nazoos_update.root import check, snapshots, update

DUP_XML = """<?xml version='1.0'?>
<stream>
<message type="info">Loading repository data...</message>
<install-summary download-size="1" space-usage-diff="1" packages-to-change="3">
<to-upgrade>
<solvable type="package" name="openSUSE-release" edition="20261018-1.1"
 edition-old="20261017-1.1" arch="x86_64" repository="repo-oss"/>
<solvable type="package" name="kernel-default" edition="7.2.12-1.1"
 edition-old="7.2.11-1.1" arch="x86_64" repository="repo-oss"/>
</to-upgrade>
<to-install>
<solvable type="patch" name="openSUSE-2026-1" edition="1" arch="noarch"/>
</to-install>
</install-summary>
</stream>
"""

PROBLEM_XML = """<?xml version='1.0'?>
<stream>
<prompt id="1"><description>Problem: nothing provides libfoo</description>
</prompt>
<problem><description>nothing provides libfoo.so.1 needed by bar</description>
</problem>
</stream>
"""

PROMPT_XML = """<?xml version='1.0'?>
<stream>
<prompt id="1"><description>Problem: 1: nothing provides 'libfoo.so.1' needed by the to be installed bar-1.0-1.1.x86_64
 Solution 1: do not install bar-1.0-1.1.x86_64
 Solution 2: break bar-1.0-1.1.x86_64 by ignoring some of its dependencies

Choose from above solutions by number or cancel [1/2/c/d/?] (c): </description>
</prompt>
</stream>
"""

# zypper >= 1.14.9 (VM 2026-10-21): "Detailed information:" + "- " lines
DETAILED_XML = """<?xml version='1.0'?>
<stream>
<prompt id="1">
<description>Problem: 1: Detailed information:
- nothing provides &apos;nazoos-x&apos; needed by the to be installed foo-2-1.noarch
- the installed foo-1-1.noarch does not belong to a distupgrade repository and must be replaced
 Solution 1: deinstallation of foo-1-1.noarch
</description>
<text>Choose from above solutions by number or cancel</text>
</prompt>
</stream>
"""


def fake_zypper(monkeypatch, stdout, rc=0):
    calls = []

    def capture(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout, "")

    monkeypatch.setattr(check, "capture", capture)
    return calls


def test_dup_preview_lists_the_changes(monkeypatch):
    calls = fake_zypper(monkeypatch, DUP_XML)
    pkgs, problems = check.dup_preview()
    assert problems == []
    assert "--dry-run" in calls[0] and "--xmlout" in calls[0]
    assert [(p["name"], p["kind"], p["type"]) for p in pkgs] == [
        ("openSUSE-release", "upgrade", "package"),
        ("kernel-default", "upgrade", "package"),
        ("openSUSE-2026-1", "install", "patch")]
    assert pkgs[0]["old"] == "20261017-1.1"


def test_dup_preview_problems(monkeypatch):
    fake_zypper(monkeypatch, PROBLEM_XML, rc=4)
    assert check.dup_preview() == (
        None, ["nothing provides libfoo.so.1 needed by bar"])


def test_dup_preview_problem_from_prompt(monkeypatch):
    fake_zypper(monkeypatch, PROMPT_XML, rc=4)
    assert check.dup_preview() == (None, [
        "nothing provides 'libfoo.so.1' needed by the to be installed "
        "bar-1.0-1.1.x86_64"])


def test_dup_preview_problem_detailed(monkeypatch):
    fake_zypper(monkeypatch, DETAILED_XML, rc=4)
    assert check.dup_preview() == (None, [
        "nothing provides 'nazoos-x' needed by the to be installed "
        "foo-2-1.noarch; the installed foo-1-1.noarch does not belong to a "
        "distupgrade repository and must be replaced"])


def test_reboot_hint_only_for_desktop_plasma():
    hint = check.REBOOT_HINT
    for name in ("plasma6-workspace", "plasma6-workspace-libs",
                 "kernel-default"):
        assert hint.match(name)
    assert not hint.match("plasma-foreground-booster")


def test_dup_preview_error_messages(monkeypatch):
    xml = ('<stream><message type="error">Repository x is invalid'
           '</message></stream>')
    fake_zypper(monkeypatch, xml, rc=8)
    with pytest.raises(Fail) as e:
        check.dup_preview()
    assert e.value.template == "zypper reported: {detail}"
    assert e.value.params == {"detail": "Repository x is invalid"}


def test_dup_preview_unreadable(monkeypatch):
    fake_zypper(monkeypatch, "not xml", rc=1)
    with pytest.raises(Fail, match="no readable answer"):
        check.dup_preview()


def release(old, new, kind="package"):
    return {"name": "openSUSE-release", "type": kind, "old": old,
            "new": new}


@pytest.mark.parametrize("pkgs, expected", [
    ([release("20261018-1.1", "20261017-1.1")], ("20261018", "20261017")),
    ([release("20261017-1.1", "20261018-1.1")], None),
    ([release("20261018-1.1", "20261017-1.1", "product")], None),
    ([release("", "20261017-1.1")], None),
    ([], None),
])
def test_mirrors_behind(pkgs, expected):
    assert check.mirrors_behind(pkgs) == expected


def label(snap, zypp_pre=(), is_update=False):
    return snapshots.snapshot_label(snap, set(zypp_pre), is_update,
                                        lambda s: s)


def test_snapshot_label_zypper_pairs():
    pre = {"number": 5, "type": "pre"}
    post = {"number": 6, "type": "post", "pre-number": 5}
    assert label(pre, {5}) == "Before software change"
    assert label(post, {5}) == "After software change"
    assert label(pre, {5}, True) == "Before update"
    assert label(post, {5}, True) == "After update"
    # A pre snapshot not made by zypper gets no name
    assert label(pre) is None


def test_snapshot_label_singles(monkeypatch):
    single = {"number": 7, "type": "single"}
    assert label(dict(single, description="timeline")) == \
        "Automatic snapshot"
    assert label(dict(single, description="mine")) == "mine"
    assert label(single) is None
    rb = dict(single, description="nazoos-update: rollback to 4")
    # The read-only backup is "Before rollback", the writable copy keeps
    # its description
    monkeypatch.setattr(snapshots.status, "subvol_readonly",
                        lambda _p: True)
    assert label(rb) == "Before rollback"
    monkeypatch.setattr(snapshots.status, "subvol_readonly",
                        lambda _p: False)
    assert label(rb) == "nazoos-update: rollback to 4"


@pytest.mark.parametrize("uefi, cert, status, expected", [
    (False, "/c.crt", "missing", False),
    (True, None, "missing", False),
    (True, "/c.crt", "enrolled", False),
    (True, "/c.crt", "pending", False),
    (True, "/c.crt", "missing", True),
])
def test_nazoos_key_missing(monkeypatch, uefi, cert, status,
                            expected):
    mok = update.mok
    monkeypatch.setattr(mok, "uefi", lambda: uefi)
    monkeypatch.setattr(mok, "signing_cert", lambda: cert)
    monkeypatch.setattr(mok, "status", lambda _c: status)
    assert update.nazoos_key_missing() is expected


def test_scriptlet_failed_names_the_package():
    line = ("warning: %post(xpadneo-ueficert-0.10.1-1.32.x86_64) "
            "scriptlet failed, exit status 255\n")
    m = update.SCRIPTLET_FAILED.search(line)
    assert m.group(1) == "xpadneo-ueficert"


@pytest.mark.parametrize("failed, covered, expected", [
    (["xpadneo-ueficert"], True, True),
    (["xpadneo-ueficert"], False, False),
    (["xpadneo-ueficert", "kernel-default"], True, False),
    ([], True, False),
])
def test_only_trusted_certs(monkeypatch, failed, covered,
                            expected):
    monkeypatch.setattr(update.helper, "output",
                        lambda cmd: "/etc/uefi\n/etc/uefi/certs/F8CEAA94.crt\n")
    monkeypatch.setattr(update.mok, "covered", lambda c: covered)
    assert update.only_trusted_certs(failed) is expected


def test_label_waits_for_snapper_cleanup(monkeypatch):
    states = iter([0, 0, 3])     # active, active, inactive
    calls = []

    def capture(cmd):
        calls.append(cmd[0])
        return subprocess.CompletedProcess(cmd, next(states), "", "")

    monkeypatch.setattr(snapshots, "capture", capture)
    monkeypatch.setattr(snapshots.time, "sleep", lambda s: None)
    snapshots.wait_for_cleanup()
    assert calls == ["systemctl"] * 3


def _fake_clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(snapshots.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(snapshots.time, "sleep",
                        lambda s: now.__setitem__(0, now[0] + s))
    return now


def test_wait_quiet_returns_after_the_stamp_was_stable(monkeypatch):
    now = _fake_clock(monkeypatch)
    calls = []

    def stamp():
        calls.append(now[0])
        return (min(len(calls), 3), None)    # changes on the first calls

    monkeypatch.setattr(snapshots, "_snapshots_stamp", stamp)
    snapshots.wait_quiet(quiet=3, timeout=60)
    # Reads at t=0, 3 (changed), 6 (changed), 9 (same)
    assert now[0] == 9


def test_wait_quiet_gives_up_at_the_timeout(monkeypatch):
    now = _fake_clock(monkeypatch)
    count = iter(range(1000))
    monkeypatch.setattr(snapshots, "_snapshots_stamp",
                        lambda: (next(count), None))
    snapshots.wait_quiet(quiet=3, timeout=10)
    assert now[0] == 12    # first sleep that ends past the timeout


def test_label_holds_the_lock_while_naming(monkeypatch, tmp_path):
    lock = tmp_path / "label.lock"
    seen = []

    def name_snapshots(update_after):
        # A second label run (the path unit) must not get in between
        with open(lock) as other:
            with pytest.raises(BlockingIOError):
                snapshots.fcntl.flock(
                    other, snapshots.fcntl.LOCK_EX
                    | snapshots.fcntl.LOCK_NB)
        seen.append(update_after)
        return 2

    monkeypatch.setattr(snapshots, "LABEL_LOCK", str(lock))
    monkeypatch.setattr(snapshots, "Path", lambda p: tmp_path)
    monkeypatch.setattr(snapshots, "wait_for_cleanup", lambda: None)
    monkeypatch.setattr(snapshots, "name_snapshots", name_snapshots)
    assert snapshots.label_snapshots(update_after=3) == 2
    assert seen == [3]


def test_check_keeps_the_restart_hint_of_the_update(monkeypatch, tmp_path):
    monkeypatch.setattr(status_mod, "STATUS", tmp_path / "status.json")
    status_mod.write({"error": "", "needs_reboot": True, "updated": 5})
    status_mod.write({"error": "", "packages": [], "reboot": False})
    st = status_mod.read_status()
    assert st["needs_reboot"] is True and st["updated"] == 5
    # The next update decides again
    status_mod.write({"error": "", "needs_reboot": False, "updated": 9})
    st = status_mod.read_status()
    assert st["needs_reboot"] is False and st["updated"] == 9


def test_failed_check_keeps_last_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(status_mod, "STATUS", tmp_path / "status.json")
    status_mod.write({"error": ""})
    ok = status_mod.read_status()["last_ok"]
    assert ok > 0
    status_mod.write({"error": status_mod.ERROR_REFRESH})
    st = status_mod.read_status()
    assert st["last_ok"] == ok and st["error"] == "refresh"


def test_update_stops_at_a_conflict(monkeypatch):
    calls, written = [], []
    monkeypatch.setattr(update, "run", lambda *a, **k: calls.append(a[0]) or 0)
    monkeypatch.setattr(check, "dup_preview", lambda *a: (None, ["x"]))
    monkeypatch.setattr(check, "flatpak_updates", lambda: [])
    monkeypatch.setattr(update.status, "write", written.append)
    with pytest.raises(Fail) as e:
        update.update([])
    assert e.value.template == "the update needs a decision: {problem}"
    assert e.value.params == {"problem": "x"}
    # Only the refresh ran, no dist-upgrade
    assert calls == [update.ZYPPER + ["--gpg-auto-import-keys", "refresh"]]
    assert written == [{"error": "conflict", "problems": ["x"], "packages": [],
                        "flatpaks": [], "reboot": False}]


def test_own_repos_are_the_enabled_nazoos_ones(monkeypatch):
    monkeypatch.setattr(check.repos, "repos", lambda: [
        ("nazoos:nazoos", "https://download.opensuse.org/x/", True),
        ("nazoos-kernel", "https://download.opensuse.org/y/", True),
        ("nazoos:nazoos-devel", "https://download.opensuse.org/z/", False),
        ("repo-oss", "https://download.opensuse.org/oss/", True)])
    assert check.own_repos() == ["nazoos:nazoos", "nazoos-kernel"]
    assert check.own_update_cmd() == [
        "update", "--auto-agree-with-licenses",
        "--repo", "nazoos:nazoos", "--repo", "nazoos-kernel"]
