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
