# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_common.mok and kernelstate without mokutil or rpm."""

import fcntl
import subprocess

import pytest

from nazoos_common import grub, helper, kernel, kernelstate, mok, repos

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
    monkeypatch.setattr(kernel.helper, "rpm_installed",
                        lambda n: n in installed)
    assert kernel.stable() is expected


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


@pytest.fixture
def repo_dir(monkeypatch, tmp_path):
    (tmp_path / "oss.repo").write_text(
        "[repo-oss]\nenabled=1\n"
        "baseurl=http://cdn.opensuse.org/tumbleweed/repo/oss/\n")
    (tmp_path / "packman.repo").write_text(
        "[packman]\nenabled=0\n"
        "baseurl=https://ftp.fau.de/packman/suse/openSUSE_Tumbleweed/\n")
    (tmp_path / "nazoos.repo").write_text(
        "[nazoos]\nbaseurl=https://example.org/tumbleweed/repo/oss/\n")
    (tmp_path / "broken.repo").write_text("no section header\n")
    monkeypatch.setattr(repos, "REPOS_DIR", tmp_path)
    return tmp_path


def test_repos_lists_every_repo_with_its_state(repo_dir):
    assert sorted(repos.repos()) == [
        ("nazoos", "https://example.org/tumbleweed/repo/oss/", True),
        ("packman",
         "https://ftp.fau.de/packman/suse/openSUSE_Tumbleweed/", False),
        ("repo-oss", "http://cdn.opensuse.org/tumbleweed/repo/oss/", True)]


def test_with_url_finds_a_disabled_repo(repo_dir):
    assert repos.with_url("/packman/") == "packman"
    assert repos.with_url("download.nvidia.com") is None


def test_repos_read_libzypp_spellings(repo_dir):
    (repo_dir / "multi.repo").write_text(
        "[multi]\nenabled=yes\n"
        "baseurl=https://download.opensuse.org/a/b/\n"
        "        https://mirror.example/a/b/\n")
    (repo_dir / "mirror.repo").write_text(
        "[pm-mirror]\nenabled=0\n"
        "mirrorlist=https://ftp.example/packman/mirrors\n")
    found = {a: (u, on) for a, u, on in repos.repos()}
    assert found["multi"] == ("https://download.opensuse.org/a/b/", True)
    assert repos.with_path("/a/b/") == "multi"
    assert found["pm-mirror"][0].endswith("/packman/mirrors")
    (repo_dir / "packman.repo").unlink()
    assert repos.with_url("/packman/") == "pm-mirror"


def test_with_path_ignores_the_mirror_host_and_other_hosts(repo_dir):
    # Same path on example.org must not match: only opensuse.org counts
    assert repos.with_path("/tumbleweed/repo/oss/") == "repo-oss"
    assert repos.with_path("/packman/") is None


def test_url_path_ignores_the_mirror_host():
    a = repos.url_path("https://download.opensuse.org/tumbleweed/repo/oss")
    b = repos.url_path("http://cdn.opensuse.org/tumbleweed/repo/oss/")
    assert a == b == "/tumbleweed/repo/oss/"


def test_services_with_their_state(monkeypatch, tmp_path):
    (tmp_path / "a.service").write_text("[openSUSE]\nenabled=1\n")
    (tmp_path / "b.service").write_text("[nazoos]\nenabled=0\n")
    monkeypatch.setattr(repos, "SERVICES_DIR", tmp_path)
    assert repos.services() == {"openSUSE": True, "nazoos": False}


def test_write_atomic_keeps_the_mode_of_an_existing_file(tmp_path):
    f = tmp_path / "conf"
    f.write_text("old")
    f.chmod(0o600)
    helper.write_atomic(f, "new\n")
    assert f.read_text() == "new\n"
    assert f.stat().st_mode & 0o777 == 0o600
    assert [x.name for x in tmp_path.iterdir()] == ["conf"]


def test_write_atomic_new_file_gets_the_mode(tmp_path):
    helper.write_atomic(str(tmp_path / "other"), "x")
    assert (tmp_path / "other").stat().st_mode & 0o777 == 0o644
    helper.write_atomic(tmp_path / "private", "x", mode=0o600)
    assert (tmp_path / "private").stat().st_mode & 0o777 == 0o600


def test_write_atomic_keeps_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.write_text("old")
    link = tmp_path / "link"
    link.symlink_to(real)
    helper.write_atomic(link, "new\n")
    assert link.is_symlink()
    assert real.read_text() == "new\n"
    assert sorted(x.name for x in tmp_path.iterdir()) == ["link", "real"]


def test_write_atomic_leaves_no_temp_file_after_a_failure(monkeypatch,
                                                          tmp_path):
    f = tmp_path / "conf"
    f.write_text("old")

    def broken(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(helper.os, "replace", broken)
    with pytest.raises(OSError):
        helper.write_atomic(f, "new\n")
    assert f.read_text() == "old"
    assert [x.name for x in tmp_path.iterdir()] == ["conf"]


def test_update_grub_default_unchanged_is_not_written(monkeypatch, tmp_path):
    default = tmp_path / "grub"
    default.write_text("A=1\n")
    monkeypatch.setattr(grub, "GRUB_LOCK", tmp_path / "lock")
    monkeypatch.setattr(grub, "GRUB_DEFAULT_FILE", default)
    monkeypatch.setattr(helper, "write_atomic", lambda *a: 1 / 0)
    assert grub.update_grub_default(lambda t: t) is False


def test_update_grub_default_without_lock_dir(monkeypatch, tmp_path):
    default = tmp_path / "grub"
    default.write_text("A=1\n")
    monkeypatch.setattr(grub, "GRUB_LOCK", tmp_path / "missing" / "lock")
    monkeypatch.setattr(grub, "GRUB_DEFAULT_FILE", default)
    assert grub.update_grub_default(lambda t: t + "B=2\n") is True
    assert default.read_text() == "A=1\nB=2\n"


def test_update_grub_default_holds_the_lock(monkeypatch, tmp_path):
    lock = tmp_path / "grub.lock"
    default = tmp_path / "grub"
    default.write_text("A=1\n")
    monkeypatch.setattr(grub, "GRUB_LOCK", lock)
    monkeypatch.setattr(grub, "GRUB_DEFAULT_FILE", default)
    held = []

    def update(text):
        with open(lock, "w") as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(False)
            except BlockingIOError:
                held.append(True)
        return text + "B=2\n"

    assert grub.update_grub_default(update) is True
    assert held == [True]
    assert default.read_text() == "A=1\nB=2\n"


@pytest.mark.parametrize("rc, stdout, expected", [
    (0, "SecureBoot enabled\n", (True, True, "SecureBoot enabled")),
    (0, "SecureBoot disabled\n", (True, False, "SecureBoot disabled")),
    (1, "", (False, False, "")),
    (OSError("no mokutil"), "", (False, False, "")),
])
def test_sb_state(monkeypatch, rc, stdout, expected):
    def run(cmd, **kw):
        if isinstance(rc, Exception):
            raise rc
        return subprocess.CompletedProcess(cmd, rc, stdout, "")

    monkeypatch.setattr(mok.subprocess, "run", run)
    assert mok.sb_state() == expected
    assert mok.uefi() is expected[0]
