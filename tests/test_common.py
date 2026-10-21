# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_common.mok and kernelstate without mokutil or rpm."""

import pytest

from nazoos_common import helper, kernelstate, mok

FPR = "SHA1 Fingerprint=AB:CD:EF:01\n"


@pytest.fixture
def tools(monkeypatch):
    """Fake answers of mokutil/openssl, by command line."""
    answers = {}

    def out(cmd):
        return answers.get(" ".join(cmd[:2]), "")

    monkeypatch.setattr(mok.proc, "out", out)
    return answers


def test_status_enrolled(tools):
    tools["mokutil --test-key"] = "/c.crt is already enrolled\n"
    assert mok.status("/c.crt") == "enrolled"


def test_enrolled_by_fingerprint_on_kernel_nazoos(tools):
    # root on a running kernel-nazoos: --test-key names the keyring
    tools["mokutil --test-key"] = ("/c.crt is already in the built-in "
                                   "trusted keyring\n")
    tools["openssl x509"] = FPR
    tools["mokutil --list-enrolled"] = "SHA1 Fingerprint: ab:cd:ef:01\n"
    assert mok.status("/c.crt") == "enrolled"


def test_status_pending_matches_the_fingerprint(tools):
    tools["openssl x509"] = FPR
    tools["mokutil --list-new"] = "SHA1 Fingerprint: ab:cd:ef:01\n"
    assert mok.status("/c.crt") == "pending"


def test_status_missing(tools):
    tools["openssl x509"] = FPR
    tools["mokutil --list-new"] = "MokNew is empty\n"
    assert mok.status("/c.crt") == "missing"
    # No fingerprint (openssl missing): never "pending"
    del tools["openssl x509"]
    assert mok.status("/c.crt") == "missing"


def test_signing_cert(tools):
    tools["rpm -ql"] = ("/boot/vmlinuz-7.2.11-1-nazoos\n"
                        "/etc/uefi/certs/4D7A1A2B.crt\n")
    assert mok.signing_cert() == "/etc/uefi/certs/4D7A1A2B.crt"
    tools["rpm -ql"] = "package kernel-nazoos is not installed\n"
    assert mok.signing_cert() is None


@pytest.fixture
def state(monkeypatch, tmp_path):
    monkeypatch.setattr(kernelstate, "STATE", tmp_path)
    monkeypatch.setattr(kernelstate, "PREFER", tmp_path / "kernel-prefer")
    monkeypatch.setattr(kernelstate, "BOOTS", tmp_path / "boots.json")
    return tmp_path


def test_boots_round_trip(state):
    assert kernelstate.read_boots() == {}
    kernelstate.write_boots({"count": 2})
    assert kernelstate.read_boots() == {"count": 2}
    (state / "boots.json").write_text("{broken")
    assert kernelstate.read_boots() == {}


@pytest.mark.parametrize("prefer, count, installed, expected", [
    (True, 3, {"kernel-default"}, True),
    (True, 2, {"kernel-default"}, False),
    (False, 5, {"kernel-default"}, False),
    (True, 3, {"kernel-default", "nazoos-kernel-only"}, False),
    (True, 3, set(), False),
])
def test_stable(monkeypatch, state, prefer, count, installed, expected):
    if prefer:
        kernelstate.PREFER.touch()
    kernelstate.write_boots({"count": count})
    monkeypatch.setattr(kernelstate.proc, "rpm_installed",
                        lambda n: n in installed)
    assert kernelstate.stable() is expected


@pytest.mark.parametrize("updated, expected", [(50, False), (150, True)])
def test_restart_clears_needs_reboot(monkeypatch, updated, expected):
    from nazoos_update import status

    monkeypatch.setattr(status, "read_status", lambda: {
        "needs_reboot": True, "updated": updated})
    monkeypatch.setattr(status.proc, "boot_time", lambda: 100)
    monkeypatch.setattr(status, "booted_snapshot", lambda: 0)
    assert status.collect()["needs_reboot"] is expected


def test_set_var_adds_replaces_and_removes():
    text = 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=0\n'
    text = helper.set_var(text, "GRUB_DEFAULT", "saved")
    assert text == 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=saved\n'
    text = helper.set_var(text, "GRUB_TOP_LEVEL", '"/boot/vmlinuz-x"')
    assert text.endswith('GRUB_TOP_LEVEL="/boot/vmlinuz-x"\n')
    text = helper.set_var(text, "GRUB_TOP_LEVEL", None)
    assert text == 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=saved\n'
    # Removing a missing variable changes nothing
    assert helper.set_var(text, "GRUB_TOP_LEVEL", None) == text


def test_set_var_appends_after_a_missing_trailing_newline():
    assert helper.set_var("A=1", "B", "2") == "A=1\nB=2\n"
    assert helper.set_var("", "B", "2") == "B=2\n"


def test_set_var_keeps_backslashes_and_escapes_the_name():
    assert helper.set_var("A=1\n", "A", r"x\ny") == "A=x\\ny\n"
    # "." in the name is not a wildcard
    assert helper.set_var("AxB=1\n", "A.B", "2") == "AxB=1\nA.B=2\n"


def test_set_var_only_matches_whole_names_at_line_start():
    text = '#GRUB_DEFAULT=0\nGRUB_DEFAULT_X=1\n'
    assert helper.set_var(text, "GRUB_DEFAULT", "saved") == \
        text + "GRUB_DEFAULT=saved\n"
