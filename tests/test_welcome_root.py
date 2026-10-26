# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parts of the welcome root actions (nothing runs as root here)."""

import io
import re
import subprocess
import types

import pytest

from nazoos_common import grub, helper, kernel, mok, proc
from nazoos_welcome import hw, system
from nazoos_welcome.pollrate import PARAM
from nazoos_welcome.root import (apps, base, drivers, drives, kernel_switch,
                                 maintenance, mok_queue, repair_fixes, tuning)

from conftest import KEY_FPR, KEY_OUTPUT, KEY_URL  # noqa: E402

MARK = hw.FSTAB_MARKER


def test_without_entry_removes_only_our_line():
    text = (f"UUID=root / btrfs defaults 0 0\n{MARK}\n"
            "UUID=abcd /mnt/Games ext4 nofail 0 0\n"
            "UUID=abcd2 /mnt/other ext4 nofail 0 0\n")
    out, mnt = drives.without_entry(text, "abcd")
    assert mnt == "/mnt/Games"
    assert out == ("UUID=root / btrfs defaults 0 0\n"
                   "UUID=abcd2 /mnt/other ext4 nofail 0 0\n")


def test_without_entry_ignores_lines_we_did_not_write():
    text = "UUID=abcd /mnt/Games ext4 nofail 0 0\n"
    assert drives.without_entry(text, "abcd") == (text, None)


def test_mount_options(monkeypatch):
    monkeypatch.setattr(drives, "unblacklist_ntfs3", lambda: None)
    assert drives.mount_options("ntfs", 1000, 100) == (
        "ntfs3", "nofail,x-systemd.device-timeout=10s,noatime,"
        "nosuid,nodev,uid=1000,gid=100,umask=022,windows_names")
    assert drives.mount_options("btrfs", 1000, 100)[1].endswith(
        ",compress=zstd:1")
    assert "uid=" not in drives.mount_options("ext4", 1000, 100)[1]
    assert ",nosuid,nodev" in drives.mount_options("ext4", 1000, 100)[1]


def test_sanitize():
    assert drives.sanitize("My Games / SSD!") == "My-Games-SSD"
    assert drives.sanitize("..") == ""
    assert len(drives.sanitize("x" * 99)) == 40


def test_pick_branch():
    assert apps.pick_branch({"23.08", "24.08"}, "23.08") == "23.08"
    assert apps.pick_branch({"9.0", "24.08", "10.1"}, "") == "24.08"


def test_kernel_install_leaves_installed_modules_to_the_swap(monkeypatch,
                                                            tmp_path):
    ks = kernel_switch
    installed = {"xone-kmp-default", "xone-kmp-nazoos"}
    calls, swapped = [], []
    monkeypatch.setattr(proc, "rpm_installed", lambda p: p in installed)
    monkeypatch.setattr(base.repos, "repos", lambda: [])
    monkeypatch.setattr(ks, "in_repo", lambda alias, p: True)
    monkeypatch.setattr(ks, "prepare_mok", lambda alias, pkgs: False)
    monkeypatch.setattr(helper, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(ks.kmp_sync, "swap_rebuilds",
                        lambda alias, names: swapped.extend(names))
    monkeypatch.setattr(ks, "say", lambda text: None)
    monkeypatch.setattr(ks.grub, "ensure_grub_default", lambda say: True)
    monkeypatch.setattr(ks.kernelstate, "STATE", tmp_path)
    monkeypatch.setattr(ks.kernelstate, "PREFER", tmp_path / "prefer")
    monkeypatch.setattr(ks.kernelstate, "write_boots", lambda data: None)
    ks.kernel_install([])
    zypper_in = [c for c in calls if "install" in c][0]
    # xone-kmp-nazoos is already there: only its rebuild is swapped
    assert "xone-kmp-nazoos" not in zypper_in
    assert ks.kernel.KERNEL_PACKAGE in zypper_in
    assert "xone-kmp-nazoos" in swapped


def kernel_env(fake_root, monkeypatch, tmp_path, repos=()):
    ks = kernel_switch
    monkeypatch.setattr(base.repos, "repos", lambda: list(repos))
    monkeypatch.setattr(ks, "in_repo", lambda alias, p: True)
    monkeypatch.setattr(ks, "prepare_mok", lambda alias, pkgs: False)
    monkeypatch.setattr(ks, "say", lambda text: None)
    monkeypatch.setattr(ks.grub, "ensure_grub_default", lambda say: True)
    monkeypatch.setattr(ks.kernelstate, "STATE", tmp_path)
    monkeypatch.setattr(ks.kernelstate, "PREFER", tmp_path / "prefer")
    monkeypatch.setattr(ks.kernelstate, "write_boots", lambda data: None)
    return ks


def zypper_words(fake_root, *words):
    return [c for c in fake_root.calls if all(w in c for w in words)]


def test_kernel_install_removes_its_repo_again_on_failure(fake_root,
                                                          monkeypatch,
                                                          tmp_path):
    ks = kernel_env(fake_root, monkeypatch, tmp_path)
    fake_root.rc = {"install": 4}
    with pytest.raises(ks.Fail):
        ks.kernel_install([])
    assert zypper_words(fake_root, "removerepo", ks.kernel.KERNEL_REPO_ALIAS)


def test_kernel_install_keeps_its_repo_when_the_kernel_is_installed(
        fake_root, monkeypatch, tmp_path):
    ks = kernel_env(fake_root, monkeypatch, tmp_path)
    fake_root.rc = {"install": 4}
    fake_root.installed = {ks.kernel.KERNEL_PACKAGE}
    with pytest.raises(ks.Fail):
        ks.kernel_install([])
    assert not zypper_words(fake_root, "removerepo")


def disabled_kernel_repo(ks):
    return [("kernel-repo", ks.kernel.KERNEL_REPO_URL, False)]


def test_kernel_install_switches_a_disabled_repo_off_again(fake_root,
                                                           monkeypatch,
                                                           tmp_path):
    ks = kernel_env(fake_root, monkeypatch, tmp_path)
    monkeypatch.setattr(base.repos, "repos",
                        lambda: disabled_kernel_repo(ks))
    fake_root.rc = {"install": 4}
    with pytest.raises(ks.Fail):
        ks.kernel_install([])
    assert zypper_words(fake_root, "modifyrepo", "--enable", "kernel-repo")
    assert zypper_words(fake_root, "modifyrepo", "--disable", "kernel-repo")
    assert not zypper_words(fake_root, "removerepo")


def test_kernel_install_success_keeps_the_repo(fake_root, monkeypatch,
                                               tmp_path):
    ks = kernel_env(fake_root, monkeypatch, tmp_path)
    monkeypatch.setattr(base.repos, "repos",
                        lambda: disabled_kernel_repo(ks))
    ks.kernel_install([])
    assert zypper_words(fake_root, "modifyrepo", "--enable", "kernel-repo")
    assert not zypper_words(fake_root, "removerepo")
    assert not zypper_words(fake_root, "modifyrepo", "--disable")


def test_kernel_install_enables_the_boot_service_when_grub_fails(
        fake_root, monkeypatch, tmp_path):
    ks = kernel_env(fake_root, monkeypatch, tmp_path)

    def broken(say):
        raise helper.Fail("x")
    monkeypatch.setattr(ks.grub, "ensure_grub_default", broken)
    with pytest.raises(helper.Fail):
        ks.kernel_install([])
    assert ["systemctl", "enable",
            "nazoos-kernel-boot.service"] in fake_root.calls


@pytest.mark.parametrize("rc, result", [(0, True), (104, False)])
def test_in_repo_reads_the_search_exit_code(monkeypatch, rc, result):
    monkeypatch.setattr(kernel_switch.zypper, "repo_search",
                        lambda alias, name: rc)
    assert kernel_switch.in_repo("a", "p") is result


def test_in_repo_raises_when_the_search_fails(monkeypatch):
    monkeypatch.setattr(kernel_switch.zypper, "repo_search",
                        lambda alias, name: 106)
    with pytest.raises(helper.Fail):
        kernel_switch.in_repo("a", "p")


def test_kernel_only_waits_for_the_clean_starts(fake_root, monkeypatch):
    ks = kernel_switch
    monkeypatch.setattr(ks, "running_nazoos", lambda: True)
    monkeypatch.setattr(ks.kernel, "stage2_now", lambda: "waiting")
    with pytest.raises(ks.Fail, match="clean starts"):
        ks.kernel_only([])
    assert not fake_root.calls


def test_kernel_only_refuses_when_not_offered(fake_root, monkeypatch):
    ks = kernel_switch
    monkeypatch.setattr(ks, "running_nazoos", lambda: True)
    monkeypatch.setattr(ks.kernel, "stage2_now", lambda: "")
    with pytest.raises(ks.Fail, match="already removed"):
        ks.kernel_only([])
    assert not fake_root.calls


def test_kernel_only_removes_the_default_kernel(fake_root, monkeypatch):
    ks = kernel_switch
    fake_root.installed = {ks.kernel.KERNEL_DEFAULT}
    monkeypatch.setattr(ks, "running_nazoos", lambda: True)
    monkeypatch.setattr(ks.kernel, "stage2_now", lambda: "ready")
    ks.kernel_only([])
    words = zypper_words(fake_root, ks.kernel.KERNEL_ONLY_PACKAGE,
                         "-" + ks.kernel.KERNEL_DEFAULT)
    assert words


def test_system_update_needs_nazoos_update(monkeypatch):
    monkeypatch.setattr(maintenance.os, "access", lambda *a: False)
    ran = []
    monkeypatch.setattr(helper, "run", lambda *a, **k: ran.append(a))
    with pytest.raises(maintenance.Fail, match="nazoos-update is not"):
        maintenance.system_update([])
    assert not ran


FSTAB_TEXT = "UUID=root / btrfs defaults 0 0\n"


@pytest.fixture
def add_env(monkeypatch, tmp_path):
    fstab = tmp_path / "fstab"
    fstab.write_text(FSTAB_TEXT)
    monkeypatch.setattr(drives, "FSTAB", fstab)
    monkeypatch.setattr(drives, "FSTAB_LOCK", tmp_path / "fstab.lock")
    monkeypatch.setattr(hw, "MOUNT_BASE", str(tmp_path / "mnt"))
    monkeypatch.setattr(drives.hw, "drives", lambda: [
        {"uuid": "abcd", "fstype": "ext4", "label": "Games",
         "managed": False}])
    monkeypatch.setattr(drives, "caller", lambda: (1000,))
    monkeypatch.setattr(helper, "output", lambda cmd: "100\n")
    monkeypatch.setattr(drives, "say", lambda *a: None)
    return fstab


def test_add_refuses_a_drive_the_gui_would_not_offer(monkeypatch, add_env):
    monkeypatch.setattr(drives.hw, "drives", lambda: [])
    ran = []
    monkeypatch.setattr(helper, "run", lambda *a, **k: ran.append(a) or 0)
    with pytest.raises(drives.Fail, match="removable or system drive"):
        drives.automount_add(["abcd"])
    assert add_env.read_text() == FSTAB_TEXT and not ran


def _failing_mount(monkeypatch):
    ran = []

    def run(cmd, check=True):
        ran.append(cmd[0])
        return 32 if cmd[0] == "mount" else 0
    monkeypatch.setattr(helper, "run", run)
    return ran


def test_add_takes_the_entry_back_when_mount_fails(monkeypatch, add_env,
                                                   tmp_path):
    ran = _failing_mount(monkeypatch)
    with pytest.raises(drives.Fail) as e:
        drives.automount_add(["abcd"])
    assert e.value.params == {"rc": 32}
    assert add_env.read_text() == FSTAB_TEXT
    assert ran == ["systemctl", "mount", "systemctl"]
    assert not (tmp_path / "mnt/Games").exists()


def test_add_keeps_a_mount_dir_that_already_existed(monkeypatch, add_env,
                                                    tmp_path):
    (tmp_path / "mnt/Games").mkdir(parents=True)
    _failing_mount(monkeypatch)
    with pytest.raises(drives.Fail):
        drives.automount_add(["abcd"])
    assert (tmp_path / "mnt/Games").is_dir()


def _remove_text(tmp_path):
    # automount_remove rmdirs the mount point: keep it out of the host's /mnt
    mnt = tmp_path / "mnt" / "Games"
    return FSTAB_TEXT + f"{MARK}\nUUID=abcd {mnt} ext4 nofail 0 0\n", mnt


def test_remove_keeps_the_entry_of_a_busy_drive(monkeypatch, add_env,
                                                fake_root, tmp_path):
    text, _ = _remove_text(tmp_path)
    add_env.write_text(text)
    monkeypatch.setattr(drives.os.path, "ismount", lambda p: True)
    fake_root.rc = {"umount": 32}
    with pytest.raises(drives.helper.Fail) as e:
        drives.automount_remove(["abcd"])
    assert e.value.params == {"rc": 32}
    assert add_env.read_text() == text


def test_remove_unmounts_a_mounted_drive(monkeypatch, add_env, fake_root,
                                         tmp_path):
    text, mnt = _remove_text(tmp_path)
    add_env.write_text(text)
    monkeypatch.setattr(drives.os.path, "ismount", lambda p: True)
    drives.automount_remove(["abcd"])
    assert add_env.read_text() == FSTAB_TEXT
    assert ["umount", str(mnt)] in fake_root.calls


def test_remove_does_not_unmount_a_drive_that_is_not_mounted(
        monkeypatch, add_env, fake_root, tmp_path):
    text, _ = _remove_text(tmp_path)
    add_env.write_text(text)
    monkeypatch.setattr(drives.os.path, "ismount", lambda p: False)
    drives.automount_remove(["abcd"])
    assert add_env.read_text() == FSTAB_TEXT
    assert not any(c[0] == "umount" for c in fake_root.calls)


def _pollrate_env(monkeypatch, tmp_path, calls):
    sysfs = tmp_path / "interrupt_interval_override"
    sysfs.write_text("\n")
    monkeypatch.setattr(tuning, "SYSFS", str(sysfs))
    monkeypatch.setattr(tuning.hw, "usb_input_devices",
                        lambda: [{"id": "046d:c08b"}])
    monkeypatch.setattr(tuning, "cmdline_set", lambda key, option: calls.append(
        (key, option(["quiet"]))))
    monkeypatch.setattr(tuning, "say", lambda *a: None)


def test_pollrate_refuses_a_device_that_is_not_connected(monkeypatch, tmp_path):
    calls = []
    _pollrate_env(monkeypatch, tmp_path, calls)
    with pytest.raises(tuning.Fail, match="not connected"):
        tuning.pollrate(["1234:abcd", "1"])
    assert not calls


def test_pollrate_sets_a_connected_device(monkeypatch, tmp_path):
    calls = []
    _pollrate_env(monkeypatch, tmp_path, calls)
    tuning.pollrate(["046d:c08b", "1"])
    assert calls == [(PARAM, f"{PARAM}=046d:c08b:1")]


def test_pollrate_too_long_leaves_grub_unchanged(monkeypatch, fake_root,
                                                 tmp_path):
    sysfs = tmp_path / "interrupt_interval_override"
    sysfs.write_text("\n")
    monkeypatch.setattr(tuning, "SYSFS", str(sysfs))
    monkeypatch.setattr(tuning.hw, "usb_input_devices",
                        lambda: [{"id": "046d:c08b"}])
    full = ",".join(f"{i:04x}:0001:1" for i in range(10))
    text = f'GRUB_CMDLINE_LINUX_DEFAULT="quiet {PARAM}={full}"\n'
    grub.GRUB_DEFAULT_FILE.write_text(text)
    with pytest.raises(tuning.Fail, match="too many"):
        tuning.pollrate(["046d:c08b", "1"])
    assert grub.GRUB_DEFAULT_FILE.read_text() == text
    assert fake_root.calls == []
    assert sysfs.read_text() == "\n"


def test_held_32bit():
    names = ["libavcodec62", "libavcodec62-32bit", "Mesa-32bit", "bash-32bit"]
    assert base.held_32bit(names) == ["Mesa-32bit", "libavcodec62-32bit"]


def test_packman_switch_keeps_32bit_when_dup_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    calls, codes = [], iter([0, 4, 0, 0, 0])

    def fake_run(cmd, check=True, **kw):
        calls.append(cmd)
        return next(codes)
    monkeypatch.setattr(helper, "run", fake_run)
    monkeypatch.setattr(helper, "output", lambda cmd: "libavcodec62-32bit\n")
    base.packman_switch("packman")
    verbs = [c[2] for c in calls]
    assert verbs == ["refresh", "dist-upgrade", "addlock",
                     "dist-upgrade", "removelock"]
    assert calls[2][3:] == ["libavcodec62-32bit"]


def test_packman_switch_fails_without_32bit(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    monkeypatch.setattr(helper, "run", lambda cmd, check=True, **kw: 0
                        if "refresh" in cmd else 4)
    monkeypatch.setattr(helper, "output", lambda cmd: "bash\n")
    with pytest.raises(base.Fail):
        base.packman_switch("packman")


def test_packman_switch_leaves_locks_of_the_user(monkeypatch, tmp_path):
    locks = tmp_path / "locks"
    locks.write_text("type: package\nsolvable_name: Mesa-32bit\n\n")
    monkeypatch.setattr(base, "ZYPP_LOCKS", locks)
    calls, codes = [], iter([0, 4, 0, 0, 0])

    def fake_run(cmd, check=True, **kw):
        calls.append(cmd)
        return next(codes)
    monkeypatch.setattr(helper, "run", fake_run)
    monkeypatch.setattr(helper, "output",
                        lambda cmd: "Mesa-32bit\nlibavcodec62-32bit\n")
    base.packman_switch("packman")
    assert calls[2][3:] == ["libavcodec62-32bit"]
    assert calls[4][3:] == ["libavcodec62-32bit"]


def test_packman_switch_fails_when_every_32bit_is_locked(monkeypatch,
                                                         tmp_path):
    locks = tmp_path / "locks"
    locks.write_text("solvable_name: Mesa-32bit\n")
    monkeypatch.setattr(base, "ZYPP_LOCKS", locks)
    monkeypatch.setattr(helper, "run", lambda cmd, check=True, **kw: 0
                        if "refresh" in cmd else 4)
    monkeypatch.setattr(helper, "output", lambda cmd: "Mesa-32bit\n")
    with pytest.raises(base.Fail):
        base.packman_switch("packman")


def test_packman_switch_honours_glob_locks(monkeypatch, tmp_path):
    locks = tmp_path / "locks"
    locks.write_text("solvable_name: Mesa*\nsolvable_name: *-32bit-x\n")
    monkeypatch.setattr(base, "ZYPP_LOCKS", locks)
    calls, codes = [], iter([0, 4, 0, 0, 0])

    def fake_run(cmd, check=True, **kw):
        calls.append(cmd)
        return next(codes)
    monkeypatch.setattr(helper, "run", fake_run)
    monkeypatch.setattr(helper, "output",
                        lambda cmd: "Mesa-32bit\nlibavcodec62-32bit\n")
    base.packman_switch("packman")
    assert calls[2][3:] == ["libavcodec62-32bit"]


PACKMAN_VENDOR = "http://packman.links2linux.de\n"


PACKMAN_URL = "https://ftp.gwdg.de/pub/linux/misc/packman/suse/x/"
NVIDIA_URL = "https://download.nvidia.com/opensuse/tumbleweed"


def _repos(monkeypatch, found):
    """FOUND: (alias, url, enabled) tuples of the repos on the system."""
    monkeypatch.setattr(base.repos, "repos", lambda: found)


def _packman_env(monkeypatch, fake_root, tmp_path, existing=None):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    _repos(monkeypatch, [] if existing is None else [existing])


def test_codecs_install_order(monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path)
    drivers.codecs_install([])
    verbs = [c[2] for c in fake_root.calls]
    assert verbs == ["addrepo", "--gpg-auto-import-keys", "refresh",
                     "dist-upgrade", "install", "install"]
    assert fake_root.calls[4][-len(system.PACKMAN_CODECS):] == (
        system.PACKMAN_CODECS)


def test_codecs_install_trusts_no_key_for_an_existing_repo(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, True))
    drivers.codecs_install([])
    assert not any("--gpg-auto-import-keys" in c for c in fake_root.calls)


def test_codecs_install_removes_the_repo_it_added_on_failure(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path)
    fake_root.rc = {"dist-upgrade": 4}
    with pytest.raises(base.Fail):
        drivers.codecs_install([])
    assert fake_root.calls[-1][2:] == ["removerepo", system.PACKMAN_ALIAS]


def test_codecs_install_keeps_the_repo_when_packman_packages_are_in(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path)
    fake_root.rc = {"dist-upgrade": 4}
    fake_root.out = lambda cmd: PACKMAN_VENDOR if "%{VENDOR}\n" in cmd else ""
    with pytest.raises(base.Fail):
        drivers.codecs_install([])
    assert not any("removerepo" in c for c in fake_root.calls)


def test_codecs_install_never_removes_a_repo_that_was_there(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, True))
    fake_root.rc = {"dist-upgrade": 4}
    with pytest.raises(base.Fail):
        drivers.codecs_install([])
    assert not any(c[2] in ("addrepo", "removerepo", "modifyrepo")
                   for c in fake_root.calls)


def test_nvidia_install_removes_the_repo_it_added_on_failure(
        monkeypatch, fake_root):
    _repos(monkeypatch, [])
    fake_root.rc = {"install": 107}
    with pytest.raises(base.Fail):
        drivers.nvidia_install(["open"])
    assert fake_root.calls[-1][2:] == ["removerepo",
                                       system.NVIDIA_REPO_ALIAS]


def test_nvidia_install_keeps_the_repo_when_a_driver_is_in(
        monkeypatch, fake_root):
    _repos(monkeypatch, [])
    fake_root.rc = {"install": 107}
    fake_root.installed = {"nvidia-video-G07"}
    with pytest.raises(base.Fail):
        drivers.nvidia_install(["open"])
    assert not any("removerepo" in c for c in fake_root.calls)


def test_repo_in_use_removes_a_new_repo_whose_key_fails(
        monkeypatch, fake_root):
    _repos(monkeypatch, [])
    fake_root.rc = {"--gpg-auto-import-keys": 1}
    # keep() would say yes, but nothing came from a repo with no key
    fake_root.installed = {"nvidia-video-G07"}
    with pytest.raises(base.Fail):
        drivers.nvidia_install(["open"])
    assert fake_root.calls[-1][2:] == ["removerepo",
                                       system.NVIDIA_REPO_ALIAS]


def test_nvidia_install_never_removes_a_repo_that_was_there(
        monkeypatch, fake_root):
    _repos(monkeypatch, [("nvidia", NVIDIA_URL, True)])
    fake_root.rc = {"install": 107}
    with pytest.raises(base.Fail):
        drivers.nvidia_install(["legacy"])
    assert not any("removerepo" in c for c in fake_root.calls)


def test_codecs_install_enables_a_disabled_repo(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, False))
    drivers.codecs_install([])
    assert fake_root.calls[0][2:] == ["modifyrepo", "--enable", "packman"]
    assert not any("addrepo" in c for c in fake_root.calls)


def test_codecs_install_disables_the_repo_it_enabled_on_failure(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, False))
    fake_root.rc = {"dist-upgrade": 4}
    with pytest.raises(base.Fail):
        drivers.codecs_install([])
    assert fake_root.calls[-1][2:] == ["modifyrepo", "--disable", "packman"]
    assert not any("removerepo" in c for c in fake_root.calls)


def test_codecs_install_disables_the_repo_even_with_packman_packages_in(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, False))
    fake_root.rc = {"dist-upgrade": 4}
    fake_root.out = lambda cmd: PACKMAN_VENDOR if "%{VENDOR}\n" in cmd else ""
    with pytest.raises(base.Fail):
        drivers.codecs_install([])
    assert fake_root.calls[-1][2:] == ["modifyrepo", "--disable", "packman"]


def test_enable_repo_prefers_an_enabled_match(monkeypatch, fake_root):
    _repos(monkeypatch, [("off", PACKMAN_URL, False),
                         ("on", PACKMAN_URL, True)])
    assert base.enable_repo("/packman/") == ("on", False)
    assert not any("modifyrepo" in c for c in fake_root.calls)


def test_nvidia_install_disables_the_repo_it_enabled_on_failure(
        monkeypatch, fake_root):
    _repos(monkeypatch, [("nvidia", NVIDIA_URL, False)])
    fake_root.rc = {"install": 107}
    with pytest.raises(base.Fail):
        drivers.nvidia_install(["open"])
    assert fake_root.calls[0][2:] == ["modifyrepo", "--enable", "nvidia"]
    assert fake_root.calls[-1][2:] == ["modifyrepo", "--disable", "nvidia"]


@pytest.mark.parametrize("installed, rpms, expected", [
    ({"nvidia-video-G07"}, "", "nvidia-open-driver-G07-signed-kmp-nazoos"),
    ({"nvidia-video-G06"}, "", "nvidia-driver-G06-kmp-nazoos"),
    # A module of another kernel flavor shows which type is in use
    (set(), "nvidia-open-driver-G06-signed-kmp-default\n",
     "nvidia-open-driver-G06-signed-kmp-nazoos"),
])
def test_repair_nvidia_picks_the_module(monkeypatch, fake_root, installed,
                                        rpms, expected):
    monkeypatch.setattr(repair_fixes.os, "uname", lambda: types.SimpleNamespace(
        release="7.2.11-1-nazoos"))
    fake_root.installed = installed
    fake_root.out = lambda cmd: rpms
    repair_fixes.repair_nvidia([])
    assert fake_root.calls[1] == repair_fixes.ZYPPER_IN + ["--force", expected]


def test_repair_nvidia_without_driver(monkeypatch, fake_root):
    monkeypatch.setattr(repair_fixes.os, "uname", lambda: types.SimpleNamespace(
        release="7.2.11-1-nazoos"))
    with pytest.raises(repair_fixes.Fail):
        repair_fixes.repair_nvidia([])


def test_firewall_zone_moves_the_interface_to_the_waydroid_zone(
        monkeypatch, fake_root):
    monkeypatch.setattr(apps.proc, "rc", lambda cmd: 0)
    apps.firewall_zone(["waydroid0"], True)
    assert fake_root.calls == [
        ["firewall-cmd", "--permanent", "--zone=nazoos-waydroid",
         "--change-interface=waydroid0"],
        ["firewall-cmd", "--reload"],
        ["firewall-cmd", "--zone=nazoos-waydroid",
         "--change-interface=waydroid0"]]
    fake_root.calls.clear()
    apps.firewall_zone(["waydroid0"], False)
    assert fake_root.calls[0][-1] == "--remove-interface=waydroid0"
    assert fake_root.calls[-1] == ["firewall-cmd", "--zone=nazoos-waydroid",
                                   "--remove-interface=waydroid0"]


def test_channel_snapshots_before_the_link_changes(monkeypatch, fake_root,
                                                   tmp_path):
    link = tmp_path / "repoindex.xml"
    monkeypatch.setattr(system, "CHANNEL_LINK", str(link))
    monkeypatch.setattr(maintenance.repos, "with_path",
                        lambda path: "nazoos:nazoos")
    link_seen = []

    def rc(cmd):
        link_seen.append(link.is_symlink())
        return 0
    fake_root.rc = rc
    maintenance.channel(["stable"])
    verbs = [c[0] if c[0] != "zypper" else c[2] for c in fake_root.calls]
    assert verbs == ["snapper", "refresh-services",
                     "refresh", "dist-upgrade"]
    assert link_seen == [False, True, True, True]
    assert link.readlink().name == "nazoos-stable-repoindex.xml"
    assert fake_root.calls[-1][-3:-1] == ["--from", "nazoos:nazoos"]


def test_channel_restores_the_link_when_the_new_repo_is_missing(
        monkeypatch, fake_root, tmp_path):
    link = tmp_path / "repoindex.xml"
    link.symlink_to("nazoos-beta-repoindex.xml")
    monkeypatch.setattr(system, "CHANNEL_LINK", str(link))
    monkeypatch.setattr(maintenance.repos, "with_path", lambda path: None)
    with pytest.raises(helper.Fail):
        maintenance.channel(["stable"])
    assert link.readlink().name == "nazoos-beta-repoindex.xml"
    assert not any("dist-upgrade" in c for c in fake_root.calls)
    assert len(zypper_words(fake_root, "refresh-services")) == 2


@pytest.mark.parametrize("unpack_rc, cpio_rc", [(1, 0), (0, 1)])
def test_cert_from_download_fails_when_unpacking_fails(
        monkeypatch, fake_root, tmp_path, unpack_rc, cpio_rc):
    cache = tmp_path / "nazoos-kernel"
    cache.mkdir()
    (cache / "kernel-nazoos-1.rpm").write_bytes(b"")
    real_path = mok_queue.Path
    monkeypatch.setattr(mok_queue, "Path", lambda p: tmp_path if str(p).endswith(
        "/packages") else real_path(p))
    cert = "/usr/share/nazoos/x.der"
    monkeypatch.setattr(mok_queue.mok, "CERT_PATH",
                        re.compile(cert))
    fake_root.out = lambda cmd: cert + "\n"

    class Unpack:
        returncode = unpack_rc
        stdout = types.SimpleNamespace(close=lambda: None)

        def __init__(self, *a, **k):
            pass

        def wait(self):
            return unpack_rc

    monkeypatch.setattr(subprocess, "Popen", Unpack)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(
        returncode=cpio_rc, stdout=b"-----BEGIN CERTIFICATE-----"))
    with pytest.raises(base.Fail, match="could not be read"):
        mok_queue.cert_from_download("nazoos-kernel")


@pytest.fixture
def no_cert(monkeypatch):
    asked = []
    monkeypatch.setattr(mok, "signing_cert",
                        lambda package: asked.append(package))
    return asked


def test_mok_import_asks_for_the_kernel_package_cert(no_cert):
    with pytest.raises(mok_queue.Fail):
        mok_queue.mok_import([])
    assert no_cert == [kernel.KERNEL_PACKAGE]


def test_prepare_mok_asks_for_the_kernel_package_cert(
        monkeypatch, fake_root, no_cert):
    monkeypatch.setattr(mok, "uefi", lambda: True)
    fake_root.installed.add(kernel.KERNEL_PACKAGE)
    with pytest.raises(mok_queue.Fail):
        mok_queue.prepare_mok("nazoos-kernel", [])
    assert no_cert == [kernel.KERNEL_PACKAGE]


GPG_COLONS = (f"pub:-:1024:17:1E8EDBE858DDEB32:1201034857:::-:::scSC:::::::\n"
              f"fpr:::::::::{KEY_FPR}:\nuid:-::::\n"
              "sub:-:2048:1:AAAA:::::e:::::::\n"
              "fpr:::::::::" + "B" * 40 + ":\n")


class FakeKeyEnv:
    """repair_key with fake zypper refresh, download and gpg."""

    def __init__(self, monkeypatch, fake_root, refresh_out=KEY_OUTPUT,
                 refresh_rc=4, colons=GPG_COLONS):
        self.captured = []
        self.fetched = []

        def capture(cmd):
            self.captured.append(cmd)
            if cmd[0] == "gpg":
                return subprocess.CompletedProcess(cmd, 0, colons, "")
            return subprocess.CompletedProcess(cmd, refresh_rc, refresh_out,
                                               "")

        def urlopen(url, timeout):
            self.fetched.append(url)
            return io.BytesIO(b"key data")
        monkeypatch.setattr(helper, "capture", capture)
        monkeypatch.setattr(helper, "UPDATE_HELPER", "/nonexistent")
        monkeypatch.setattr(repair_fixes.repos, "repos",
                            lambda: [("keytest", "https://x/", True)])
        monkeypatch.setattr(repair_fixes.repos, "alias_of", lambda label: (
            "keytest" if label == "Some Name (beta)" else None))
        monkeypatch.setattr(repair_fixes.urllib.request, "urlopen", urlopen)
        self.fake = fake_root

    def verbs(self):
        return [c[0:2] if c[0] == "rpm" else c[2] for c in self.fake.calls]


@pytest.mark.parametrize("args", [
    ["keytest", "4AFF"], ["keytest", KEY_FPR.lower()],
    ["other", KEY_FPR], ["keytest"]])
def test_repair_key_rejects_bad_arguments(monkeypatch, fake_root, args):
    env = FakeKeyEnv(monkeypatch, fake_root)
    with pytest.raises(helper.Fail):
        repair_fixes.repair_key(args)
    assert env.captured == [] and fake_root.calls == []


def test_repair_key_refuses_a_different_fingerprint(monkeypatch, fake_root):
    env = FakeKeyEnv(monkeypatch, fake_root)
    with pytest.raises(helper.Fail) as e:
        repair_fixes.repair_key(["keytest", "A" * 40])
    assert "different" in e.value.template
    assert env.fetched == [] and fake_root.calls == []


def test_repair_key_refuses_a_key_file_with_another_fingerprint(
        monkeypatch, fake_root):
    FakeKeyEnv(monkeypatch, fake_root, colons=GPG_COLONS.replace(KEY_FPR,
                                                                 "C" * 40))
    with pytest.raises(helper.Fail) as e:
        repair_fixes.repair_key(["keytest", KEY_FPR])
    assert "does not match" in e.value.template
    assert not any(c[0] == "rpm" for c in fake_root.calls)


def test_repair_key_imports_the_matching_key(monkeypatch, fake_root):
    env = FakeKeyEnv(monkeypatch, fake_root)
    repair_fixes.repair_key(["keytest", KEY_FPR])
    assert env.fetched == [KEY_URL]
    gpg = next(c for c in env.captured if c[0] == "gpg")
    assert "--homedir" in gpg and "--show-keys" in gpg
    # gpg checks the file, rpm gets gpg's own export of that key
    assert [c[:2] if c[0] in ("rpm", "gpg") else c[2]
            for c in fake_root.calls] == [["gpg", "--batch"],
                                          ["rpm", "--import"], "refresh"]
    assert fake_root.calls[1][-1].endswith("clean.asc")
    export = env.captured[-1]
    assert "--export" in export and export[-1] == KEY_FPR


def test_repair_key_ignores_plain_http_urls(monkeypatch, fake_root):
    env = FakeKeyEnv(monkeypatch, fake_root,
                     refresh_out=KEY_OUTPUT.replace("https://", "http://"))
    with pytest.raises(helper.Fail):
        repair_fixes.repair_key(["keytest", KEY_FPR])
    assert env.fetched == []


@pytest.mark.parametrize("colons", [
    GPG_COLONS.replace("pub:-:", "pub:r:"),
    GPG_COLONS.replace("pub:-:", "pub:e:"),
    # the requested fingerprint belongs to a subkey of another primary
    GPG_COLONS.replace(f"fpr:::::::::{KEY_FPR}:", "fpr:::::::::" + "D" * 40
                       + ":").replace("B" * 40, KEY_FPR),
])
def test_repair_key_rejects_unusable_key_files(monkeypatch, fake_root,
                                               colons):
    FakeKeyEnv(monkeypatch, fake_root, colons=colons)
    with pytest.raises(helper.Fail):
        repair_fixes.repair_key(["keytest", KEY_FPR])
    assert not any(c[0] == "rpm" for c in fake_root.calls)


def test_repair_key_when_the_key_is_already_trusted(monkeypatch, fake_root):
    env = FakeKeyEnv(monkeypatch, fake_root, refresh_out="", refresh_rc=0)
    repair_fixes.repair_key(["keytest", KEY_FPR])
    assert env.fetched == [] and fake_root.calls == []


def test_repair_key_fails_when_the_refresh_fails_otherwise(
        monkeypatch, fake_root):
    FakeKeyEnv(monkeypatch, fake_root, refresh_out="no route", refresh_rc=4)
    with pytest.raises(helper.Fail) as e:
        repair_fixes.repair_key(["keytest", KEY_FPR])
    assert "could not be refreshed" in e.value.template


LIVEMEDIA = ("Problem: 1: nothing provides 'libliveMedia.so.120()(64bit)' "
             "needed by the to be installed "
             "vlc-noX-3.0.24-1699.9.pm.3.x86_64\n")


@pytest.mark.parametrize("text", [
    LIVEMEDIA,
    " - nothing provides 'libliveMedia.so.120()(64bit)' needed by the to be "
    "installed vlc-noX-3.0.24-1699.9.pm.3.x86_64\n",
    "  the to be installed vlc-noX-3.0.24-1699.9.pm.3.x86_64 requires "
    "'libliveMedia.so.120()(64bit)', but this requirement cannot be "
    "provided\n",
])
def test_unresolvable_wordings(text):
    assert base.unresolvable(text) == ["vlc-noX"]


def test_unresolvable_several_and_32bit():
    text = (LIVEMEDIA
            + "nothing provides 'libx.so.1' needed by the to be installed "
              "libfoo-32bit-1.2-3.1.i586\n"
            + "nothing provides 'y' needed by the to be installed "
              "ffmpeg-7-1.noarch\n"
            + LIVEMEDIA + "unrelated line needed by nothing\n")
    assert base.unresolvable(text) == ["ffmpeg", "libfoo-32bit", "vlc-noX"]
    assert base.unresolvable("") == []


def _dup_that_fails(monkeypatch, tmp_path, outputs):
    """helper.run fake: refresh/addlock/removelock work, every dup fails
    printing the next of OUTPUTS (the last one repeats)."""
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    calls = []

    def fake_run(cmd, check=True, on_line=None):
        calls.append(cmd)
        if cmd[2] == "dist-upgrade":
            n = len([c for c in calls if c[2] == "dist-upgrade"])
            on_line(outputs[min(n, len(outputs)) - 1])
            return 4
        return 0
    monkeypatch.setattr(helper, "run", fake_run)
    monkeypatch.setattr(helper, "output", lambda cmd: "bash\n")
    return calls


def test_packman_switch_locks_the_unresolvable_package(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    calls, codes = [], iter([0, 4, 0, 0, 0])

    def fake_run(cmd, check=True, on_line=None):
        calls.append(cmd)
        rc = next(codes)
        if on_line and rc:
            on_line(LIVEMEDIA)
        return rc
    monkeypatch.setattr(helper, "run", fake_run)
    monkeypatch.setattr(helper, "output", lambda cmd: "bash\n")
    base.packman_switch("packman")
    assert [c[2] for c in calls] == ["refresh", "dist-upgrade", "addlock",
                                     "dist-upgrade", "removelock"]
    assert calls[2][3:] == ["vlc-noX", "vlc-noX-32bit"]
    assert calls[4][3:] == ["vlc-noX", "vlc-noX-32bit"]


def test_packman_switch_says_packman_is_rebuilding(monkeypatch, tmp_path):
    calls = _dup_that_fails(monkeypatch, tmp_path, [LIVEMEDIA])
    with pytest.raises(helper.Fail) as e:
        base.packman_switch("packman")
    assert e.value.template.startswith("Packman is rebuilding")
    assert e.value.params == {"packages": "vlc-noX"}
    # Nothing new to hold the second time: two dups, locks removed
    assert [c[2] for c in calls] == ["refresh", "dist-upgrade", "addlock",
                                     "dist-upgrade", "removelock"]


def test_packman_switch_stops_after_three_tries(monkeypatch, tmp_path):
    outs = [LIVEMEDIA, LIVEMEDIA.replace("vlc-noX", "other"),
            LIVEMEDIA.replace("vlc-noX", "third")]
    calls = _dup_that_fails(monkeypatch, tmp_path, outs)
    with pytest.raises(helper.Fail) as e:
        base.packman_switch("packman")
    assert len([c for c in calls if c[2] == "dist-upgrade"]) == 3
    assert e.value.params == {"packages": "other, third, vlc-noX"}
    assert calls[-1][2] == "removelock"


def test_packman_switch_leaves_user_locks_of_unresolvable_names(
        monkeypatch, tmp_path):
    locks = tmp_path / "locks"
    locks.write_text("solvable_name: vlc-noX\n")
    calls = _dup_that_fails(monkeypatch, tmp_path, [LIVEMEDIA])
    monkeypatch.setattr(base, "ZYPP_LOCKS", locks)
    with pytest.raises(helper.Fail):
        base.packman_switch("packman")
    # Only -32bit is ours; the user's lock is neither added nor removed
    assert [c[3:] for c in calls if c[2] == "addlock"] == [["vlc-noX-32bit"]]
    assert [c[3:] for c in calls if c[2] == "removelock"] == [
        ["vlc-noX-32bit"]]


def test_packman_switch_other_failure_is_not_a_rebuild(monkeypatch,
                                                       tmp_path):
    outs = [LIVEMEDIA, "Problem: conflict\n"]
    _dup_that_fails(monkeypatch, tmp_path, outs)
    with pytest.raises(helper.Fail) as e:
        base.packman_switch("packman")
    assert e.value.template.startswith("'{cmd}' failed")


def test_unresolvable_name_cannot_be_an_option():
    assert base.unresolvable("needed by the to be installed "
                             "--help-1-2.noarch\n") == []
