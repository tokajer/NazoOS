# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-update-helper: zypper XML, mirror check, snapshot names."""

import subprocess

import pytest

from nazoos_common.helper import Fail

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


def fake_zypper(monkeypatch, helper, stdout, rc=0):
    calls = []

    def capture(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout, "")

    monkeypatch.setattr(helper, "capture", capture)
    return calls


def test_dup_preview_lists_the_changes(monkeypatch, update_helper):
    calls = fake_zypper(monkeypatch, update_helper, DUP_XML)
    pkgs, problems = update_helper.dup_preview()
    assert problems == []
    assert "--dry-run" in calls[0] and "--xmlout" in calls[0]
    assert [(p["name"], p["kind"], p["type"]) for p in pkgs] == [
        ("openSUSE-release", "upgrade", "package"),
        ("kernel-default", "upgrade", "package"),
        ("openSUSE-2026-1", "install", "patch")]
    assert pkgs[0]["old"] == "20261017-1.1"


def test_dup_preview_problems(monkeypatch, update_helper):
    fake_zypper(monkeypatch, update_helper, PROBLEM_XML, rc=4)
    assert update_helper.dup_preview() == (
        None, ["nothing provides libfoo.so.1 needed by bar"])


def test_dup_preview_problem_from_prompt(monkeypatch, update_helper):
    fake_zypper(monkeypatch, update_helper, PROMPT_XML, rc=4)
    assert update_helper.dup_preview() == (None, [
        "nothing provides 'libfoo.so.1' needed by the to be installed "
        "bar-1.0-1.1.x86_64"])


def test_dup_preview_problem_detailed(monkeypatch, update_helper):
    fake_zypper(monkeypatch, update_helper, DETAILED_XML, rc=4)
    assert update_helper.dup_preview() == (None, [
        "nothing provides 'nazoos-x' needed by the to be installed "
        "foo-2-1.noarch; the installed foo-1-1.noarch does not belong to a "
        "distupgrade repository and must be replaced"])


def test_reboot_hint_only_for_desktop_plasma(update_helper):
    hint = update_helper.REBOOT_HINT
    for name in ("plasma6-workspace", "plasma6-workspace-libs",
                 "kernel-default"):
        assert hint.match(name)
    assert not hint.match("plasma-foreground-booster")


def test_dup_preview_error_messages(monkeypatch, update_helper):
    xml = ('<stream><message type="error">Repository x is invalid'
           '</message></stream>')
    fake_zypper(monkeypatch, update_helper, xml, rc=8)
    with pytest.raises(Fail) as e:
        update_helper.dup_preview()
    assert e.value.template == "zypper reported: {detail}"
    assert e.value.params == {"detail": "Repository x is invalid"}


def test_dup_preview_unreadable(monkeypatch, update_helper):
    fake_zypper(monkeypatch, update_helper, "not xml", rc=1)
    with pytest.raises(Fail, match="no readable answer"):
        update_helper.dup_preview()


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
def test_mirrors_behind(update_helper, pkgs, expected):
    assert update_helper.mirrors_behind(pkgs) == expected


def label(update_helper, snap, zypp_pre=(), is_update=False):
    return update_helper.snapshot_label(snap, set(zypp_pre), is_update,
                                        lambda s: s)


def test_snapshot_label_zypper_pairs(update_helper):
    pre = {"number": 5, "type": "pre"}
    post = {"number": 6, "type": "post", "pre-number": 5}
    assert label(update_helper, pre, {5}) == "Before software change"
    assert label(update_helper, post, {5}) == "After software change"
    assert label(update_helper, pre, {5}, True) == "Before update"
    assert label(update_helper, post, {5}, True) == "After update"
    # A pre snapshot not made by zypper gets no name
    assert label(update_helper, pre) is None


def test_snapshot_label_singles(monkeypatch, update_helper):
    single = {"number": 7, "type": "single"}
    assert label(update_helper, dict(single, description="timeline")) == \
        "Automatic snapshot"
    assert label(update_helper, dict(single, description="mine")) == "mine"
    assert label(update_helper, single) is None
    rb = dict(single, description="nazoos-update: rollback to 4")
    # The read-only backup is "Before rollback", the writable copy keeps
    # its description
    monkeypatch.setattr(update_helper.status, "subvol_readonly",
                        lambda _p: True)
    assert label(update_helper, rb) == "Before rollback"
    monkeypatch.setattr(update_helper.status, "subvol_readonly",
                        lambda _p: False)
    assert label(update_helper, rb) == "nazoos-update: rollback to 4"


@pytest.mark.parametrize("uefi, cert, status, expected", [
    (False, "/c.crt", "missing", False),
    (True, None, "missing", False),
    (True, "/c.crt", "enrolled", False),
    (True, "/c.crt", "pending", False),
    (True, "/c.crt", "missing", True),
])
def test_nazoos_key_missing(monkeypatch, update_helper, uefi, cert, status,
                            expected):
    mok = update_helper.mok
    monkeypatch.setattr(mok, "uefi", lambda: uefi)
    monkeypatch.setattr(mok, "signing_cert", lambda: cert)
    monkeypatch.setattr(mok, "status", lambda _c: status)
    assert update_helper.nazoos_key_missing() is expected


def test_scriptlet_failed_names_the_package(update_helper):
    line = ("warning: %post(xpadneo-ueficert-0.10.1-1.32.x86_64) "
            "scriptlet failed, exit status 255\n")
    m = update_helper.SCRIPTLET_FAILED.search(line)
    assert m.group(1) == "xpadneo-ueficert"


@pytest.mark.parametrize("failed, covered, expected", [
    (["xpadneo-ueficert"], True, True),
    (["xpadneo-ueficert"], False, False),
    (["xpadneo-ueficert", "kernel-default"], True, False),
    ([], True, False),
])
def test_only_trusted_certs(monkeypatch, update_helper, failed, covered,
                            expected):
    monkeypatch.setattr(update_helper.helper, "output",
                        lambda cmd: "/etc/uefi\n/etc/uefi/certs/F8CEAA94.crt\n")
    monkeypatch.setattr(update_helper.mok, "covered", lambda c: covered)
    assert update_helper.only_trusted_certs(failed) is expected


def test_label_waits_for_snapper_cleanup(monkeypatch, update_helper):
    states = iter([0, 0, 3])     # active, active, inactive
    calls = []

    def capture(cmd):
        calls.append(cmd[0])
        return subprocess.CompletedProcess(cmd, next(states), "", "")

    monkeypatch.setattr(update_helper, "capture", capture)
    monkeypatch.setattr(update_helper.time, "sleep", lambda s: None)
    update_helper.wait_for_cleanup()
    assert calls == ["systemctl"] * 3


def test_label_holds_the_lock_while_naming(monkeypatch, tmp_path,
                                           update_helper):
    lock = tmp_path / "label.lock"
    seen = []

    def name_snapshots(update_after):
        # A second label run (the path unit) must not get in between
        with open(lock) as other:
            with pytest.raises(BlockingIOError):
                update_helper.fcntl.flock(
                    other, update_helper.fcntl.LOCK_EX
                    | update_helper.fcntl.LOCK_NB)
        seen.append(update_after)
        return 2

    monkeypatch.setattr(update_helper, "LABEL_LOCK", str(lock))
    monkeypatch.setattr(update_helper, "Path", lambda p: tmp_path)
    monkeypatch.setattr(update_helper, "wait_for_cleanup", lambda: None)
    monkeypatch.setattr(update_helper, "name_snapshots", name_snapshots)
    assert update_helper.label_snapshots(update_after=3) == 2
    assert seen == [3]
