# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-update: zypper XML, mirror check, snapshot names."""

import fcntl
import re
import subprocess
import threading
from pathlib import Path

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


def test_nazoos_key_missing_is_false_when_mokutil_is_broken(monkeypatch):
    def broken(cert, strict=False):
        raise Fail("x")
    monkeypatch.setattr(update.mok, "uefi", lambda: True)
    monkeypatch.setattr(update.mok, "signing_cert", lambda pkg: "/c.crt")
    monkeypatch.setattr(update.mok, "status", broken)
    assert update.nazoos_key_missing() is False


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
        [], ["nothing provides libfoo.so.1 needed by bar"])


def test_dup_preview_problem_from_prompt(monkeypatch):
    fake_zypper(monkeypatch, PROMPT_XML, rc=4)
    assert check.dup_preview() == ([], [
        "nothing provides 'libfoo.so.1' needed by the to be installed "
        "bar-1.0-1.1.x86_64"])


def test_dup_preview_problem_detailed(monkeypatch):
    fake_zypper(monkeypatch, DETAILED_XML, rc=4)
    assert check.dup_preview() == ([], [
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
    # The read-only backup is "Before rollback", the writable copy is
    # "After rollback"
    monkeypatch.setattr(snapshots.status, "subvol_readonly",
                        lambda _p: True)
    assert label(rb) == "Before rollback"
    monkeypatch.setattr(snapshots.status, "subvol_readonly",
                        lambda _p: False)
    # Unreadable path also gives False: no "After rollback" without the dir
    assert label(rb) == "nazoos-update: rollback to 4"
    monkeypatch.setattr(snapshots.Path, "is_dir", lambda _self: True)
    assert label(rb) == "After rollback"
    assert label(dict(single, description="nazoos-welcome: manual snapshot")
                 ) == "Manual snapshot"
    assert label(dict(single, description="nazoos-welcome: before "
                      "switching to beta")) == "Before channel switch"


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
    monkeypatch.setattr(mok, "signing_cert", lambda _p: cert)
    monkeypatch.setattr(mok, "status", lambda _c, strict=False: status)
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
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        seen.append(update_after)
        return 2

    monkeypatch.setattr(snapshots, "LABEL_LOCK", str(lock))
    monkeypatch.setattr(snapshots.proc, "has", lambda name: True)
    monkeypatch.setattr(snapshots, "Path", lambda p: tmp_path)
    monkeypatch.setattr(snapshots, "wait_for_cleanup", lambda: None)
    monkeypatch.setattr(snapshots, "name_snapshots", name_snapshots)
    assert snapshots.label_snapshots(update_after=3) == 2
    assert seen == [3]


def test_update_waits_for_a_running_check(monkeypatch, tmp_path, capfd):
    from nazoos_update import root

    lock = tmp_path / "action.lock"
    monkeypatch.setattr(root, "ACTION_LOCK", str(lock))
    ran = []
    monkeypatch.setattr(root.update, "update", ran.append)
    with open(lock, "w") as running:
        # A timer check is still asking Flathub: the update waits for it
        fcntl.flock(running, fcntl.LOCK_EX)
        t = threading.Thread(target=root.ACTIONS["update"], args=(["x"],))
        t.start()
        t.join(0.5)
        assert t.is_alive() and ran == []
    t.join(5)
    assert ran == [["x"]]
    assert "Waiting for the running update check" in capfd.readouterr().out


def test_update_goes_on_after_waiting_too_long(monkeypatch, tmp_path, capfd):
    from nazoos_update import root

    lock = tmp_path / "action.lock"
    monkeypatch.setattr(root, "ACTION_LOCK", str(lock))
    monkeypatch.setattr(root, "UPDATE_WAIT", 0)
    ran = []
    monkeypatch.setattr(root.update, "update", ran.append)
    with open(lock, "w") as hanging:
        fcntl.flock(hanging, fcntl.LOCK_EX)
        root.ACTIONS["update"](["x"])
    assert ran == [["x"]]
    assert "updating anyway" in capfd.readouterr().out


def test_check_never_waits(monkeypatch, tmp_path, capfd):
    # A waiting check could deadlock against an update that restarts the
    # check service from its package scripts
    from nazoos_update import root

    lock = tmp_path / "action.lock"
    monkeypatch.setattr(root, "ACTION_LOCK", str(lock))
    ran = []
    monkeypatch.setattr(root.check, "check", ran.append)
    with open(lock, "w") as updating:
        fcntl.flock(updating, fcntl.LOCK_EX)
        root.ACTIONS["check"]([])
    assert ran == []
    assert "nothing to do" in capfd.readouterr().out
    root.ACTIONS["check"]([])
    assert ran == [[]]
    # rollback and label write no status and never wait
    assert root.ACTIONS["rollback"] is snapshots.rollback
    assert root.ACTIONS["label"] is snapshots.label


def test_check_keeps_the_restart_hint_of_the_update(monkeypatch, tmp_path):
    monkeypatch.setattr(status_mod, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(status_mod, "STATUS_LOCK", tmp_path / "status.lock")
    status_mod.write({"error": "", "needs_reboot": True, "updated": 5})
    status_mod.write(status_mod.new())
    st = status_mod.read_status()
    assert st["needs_reboot"] is True and st["updated"] == 5
    # The next update decides again
    status_mod.write({"error": "", "needs_reboot": False, "updated": 9})
    st = status_mod.read_status()
    assert st["needs_reboot"] is False and st["updated"] == 9


def test_failed_check_keeps_last_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(status_mod, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(status_mod, "STATUS_LOCK", tmp_path / "status.lock")
    status_mod.write({"error": ""})
    ok = status_mod.read_status()["last_ok"]
    assert ok > 0
    status_mod.write({"error": status_mod.ERROR_REFRESH})
    st = status_mod.read_status()
    assert st["last_ok"] == ok and st["error"] == "refresh"


def test_update_stops_at_a_conflict(monkeypatch):
    calls, written = [], []
    monkeypatch.setattr(update, "run", lambda *a, **k: calls.append(a[0]) or 0)
    monkeypatch.setattr(check, "dup_preview", lambda *a: ([], ["x"]))
    monkeypatch.setattr(check, "flatpak_updates", lambda: [])
    monkeypatch.setattr(update.status, "write", written.append)
    with pytest.raises(Fail) as e:
        update.update([])
    assert e.value.template == "the update needs a decision: {problem}"
    assert e.value.params == {"problem": "x"}
    # Only the refresh ran, no dist-upgrade
    assert calls == [update.zypper.ZYPPER + ["refresh"]]
    assert written == [status_mod.new(error=status_mod.ERROR_CONFLICT, problems=["x"])]


@pytest.mark.parametrize("clean", [False, True])
def test_unused_flatpaks_go_only_when_chosen(monkeypatch, clean):
    calls = []
    monkeypatch.setattr(update, "run", lambda *a, **k: calls.append(a[0]) or 0)
    monkeypatch.setattr(update.proc, "has", lambda _name: True)
    monkeypatch.setattr(update.kernel, "keep_default", lambda _say: None)
    update.after_update_extras(False, clean)
    unused = update.FLATPAK + ["uninstall", "--unused", "--noninteractive", "-y"]
    assert (unused in calls) is clean
    assert update.FLATPAK + ["update", "--noninteractive", "-y"] in calls


def test_update_keeps_flatpaks_that_failed_to_update(monkeypatch):
    written = []
    monkeypatch.setattr(update, "run", lambda *a, **k: 0)
    monkeypatch.setattr(check, "dup_preview", lambda *a: ([], []))
    monkeypatch.setattr(check, "mirrors_behind", lambda _pkgs: None)
    monkeypatch.setattr(update, "run_dup", lambda _cmd: False)
    monkeypatch.setattr(update, "after_update_extras", lambda *a: None)
    monkeypatch.setattr(update, "capture",
                        lambda cmd: subprocess.CompletedProcess(cmd, 0))
    # flatpak update failed (check=False): the app is still pending
    monkeypatch.setattr(check, "flatpak_updates", lambda: ["org.x.App//stable"])
    monkeypatch.setattr(update.status, "write", written.append)
    update.update([])
    assert written[-1]["flatpaks"] == ["org.x.App//stable"]
    assert written[-1]["packages"] == [] and written[-1]["error"] == ""


def test_update_rejects_unknown_arguments():
    with pytest.raises(Fail):
        update.update(["--unused"])


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


@pytest.mark.parametrize("rc, trusted, key_missing, expected", [
    (0, False, False, update.OK),
    (107, True, False, update.OK),
    (107, False, True, update.KEY_MISSING),
    (107, False, False, update.FAIL),
    (1, False, False, update.FAIL),
])
def test_script_failure(monkeypatch, rc, trusted, key_missing, expected):
    monkeypatch.setattr(update, "only_trusted_certs", lambda failed: trusted)
    monkeypatch.setattr(update, "nazoos_key_missing", lambda: key_missing)
    assert update.script_failure(rc, ["x-ueficert"]) == expected


def test_failed_snapper_modify_is_reported_not_counted(monkeypatch, capsys):
    monkeypatch.setattr(snapshots, "snapshots", lambda: [
        {"number": 5, "type": "single", "description": "manual",
         "date": "2026-10-25 10:00:00"}])
    calls = []

    def capture(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    monkeypatch.setattr(snapshots, "capture", capture)
    assert snapshots.name_snapshots(None) == 0
    assert len(calls) == 1
    assert "snapshot 5 could not be named: boom" in capsys.readouterr().out


def _refresh_fails(monkeypatch, tmp_path, stdout):
    monkeypatch.setattr(status_mod, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(status_mod, "STATUS_LOCK", tmp_path / "status.lock")
    monkeypatch.setattr(check, "capture", lambda cmd: subprocess.CompletedProcess(
        cmd, 4, stdout, ""))


def test_check_with_an_unknown_repo_key(monkeypatch, tmp_path):
    from conftest import KEY_FPR, KEY_OUTPUT
    _refresh_fails(monkeypatch, tmp_path, KEY_OUTPUT)
    monkeypatch.setattr(check.repos, "alias_of", lambda label: "keytest")
    with pytest.raises(Fail) as e:
        check.check()
    assert e.value.template == ("the signing key of repository {repo} "
                                "is unknown or has changed")
    assert e.value.params == {"repo": "Some Name (beta)"}
    st = status_mod.read_status()
    assert st["error"] == "key"
    assert st["keys"] == [{
        "repo": "keytest", "label": "Some Name (beta)",
        "fingerprint": KEY_FPR,
        "shown": "Some Name (beta): " + " ".join(
            KEY_FPR[i:i + 4] for i in range(0, 40, 4))}]


def test_check_without_a_network_stays_a_refresh_error(monkeypatch, tmp_path):
    _refresh_fails(monkeypatch, tmp_path, "Could not resolve host\n")
    with pytest.raises(Fail) as e:
        check.check()
    assert "no internet" in e.value.template
    st = status_mod.read_status()
    assert st["error"] == "refresh" and st["keys"] == []


def test_check_unit_accepts_the_recorded_exit_code():
    unit = (Path(__file__).resolve().parent.parent
            / "packages/nazoos-update/data/nazoos-update-check.service")
    m = re.search(r"^SuccessExitStatus=(\d+)$", unit.read_text(), re.M)
    assert m and int(m.group(1)) == check.Recorded.rc


def test_read_status_ignores_other_json(monkeypatch, tmp_path):
    f = tmp_path / "status.json"
    monkeypatch.setattr(status_mod, "STATUS", f)
    f.write_text("[1, 2]")
    assert status_mod.read_status() == {}
    f.write_text('{"count": 2}')
    assert status_mod.read_status() == {"count": 2}


@pytest.mark.parametrize("rc, expected", [(0, (["org.x.App//stable"], False)),
                                          (1, ([], True))])
def test_failed_flatpak_query_is_not_up_to_date(monkeypatch, rc, expected):
    # Flathub unreachable: no list, and the GUI must not say "up to date"
    monkeypatch.setattr(check.proc, "has", lambda _name: True)
    monkeypatch.setattr(check, "say", lambda *a, **k: None)
    monkeypatch.setattr(check, "capture", lambda cmd: subprocess.CompletedProcess(
        cmd, rc, "org.x.App\tstable\n" if rc == 0 else "", "error"))
    st = check.flatpak_status()
    assert (st["flatpaks"], st["flatpak_failed"]) == expected
