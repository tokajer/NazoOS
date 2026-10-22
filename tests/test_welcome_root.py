# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parts of the welcome root actions (nothing runs as root here)."""

import types

import pytest

from nazoos_welcome import catalog
from nazoos_welcome.root import (apps, base, drivers, drives, kernel_switch,
                                 maintenance, repairs, tuning)

MARK = catalog.FSTAB_MARKER


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
        "uid=1000,gid=100,umask=022,windows_names")
    assert drives.mount_options("btrfs", 1000, 100)[1].endswith(
        ",compress=zstd:1")
    assert "uid=" not in drives.mount_options("ext4", 1000, 100)[1]


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
    monkeypatch.setattr(ks, "rpm_installed", lambda p: p in installed)
    monkeypatch.setattr(ks.kernel, "kernel_repo", lambda: "nazoos-kernel")
    monkeypatch.setattr(ks, "repo_has", lambda alias, p: True)
    monkeypatch.setattr(ks, "prepare_mok", lambda alias, pkgs: False)
    monkeypatch.setattr(ks, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(ks.kernel, "swap_rebuilds",
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


FSTAB_TEXT = "UUID=root / btrfs defaults 0 0\n"


@pytest.fixture
def add_env(monkeypatch, tmp_path):
    fstab = tmp_path / "fstab"
    fstab.write_text(FSTAB_TEXT)
    monkeypatch.setattr(drives, "FSTAB", fstab)
    monkeypatch.setattr(catalog, "MOUNT_BASE", str(tmp_path / "mnt"))
    monkeypatch.setattr(drives.probes, "drives", lambda: [
        {"uuid": "abcd", "fstype": "ext4", "label": "Games",
         "managed": False}])
    monkeypatch.setattr(drives, "caller", lambda: (1000,))
    monkeypatch.setattr(drives, "output", lambda cmd: "100\n")
    monkeypatch.setattr(drives, "say", lambda *a: None)
    return fstab


def test_add_refuses_a_drive_the_gui_would_not_offer(monkeypatch, add_env):
    monkeypatch.setattr(drives.probes, "drives", lambda: [])
    ran = []
    monkeypatch.setattr(drives, "run", lambda *a, **k: ran.append(a) or 0)
    with pytest.raises(drives.Fail, match="removable or system drive"):
        drives.automount_add(["abcd"])
    assert add_env.read_text() == FSTAB_TEXT and not ran


def _failing_mount(monkeypatch):
    ran = []

    def run(cmd, check=True):
        ran.append(cmd[0])
        return 32 if cmd[0] == "mount" else 0
    monkeypatch.setattr(drives, "run", run)
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


def _pollrate_env(monkeypatch, tmp_path, calls):
    sysfs = tmp_path / "interrupt_interval_override"
    sysfs.write_text("\n")
    monkeypatch.setattr(catalog, "POLLRATE_SYSFS", str(sysfs))
    monkeypatch.setattr(tuning.probes, "usb_input_devices",
                        lambda: [{"id": "046d:c08b"}])
    grub_file = tmp_path / "grub"
    grub_file.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n')
    monkeypatch.setattr(tuning.grub, "GRUB_DEFAULT_FILE", grub_file)
    monkeypatch.setattr(tuning, "cmdline_set", lambda *a: calls.append(a))
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
    assert calls and calls[0][0] == catalog.POLLRATE_PARAM


def test_held_32bit():
    names = "libavcodec62\nlibavcodec62-32bit\nMesa-32bit\nbash-32bit\n"
    assert base.held_32bit(names) == ["Mesa-32bit", "libavcodec62-32bit"]


def test_packman_switch_keeps_32bit_when_dup_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    calls, codes = [], iter([0, 4, 0, 0, 0])

    def fake_run(cmd, check=True, **kw):
        calls.append(cmd)
        return next(codes)
    monkeypatch.setattr(base, "run", fake_run)
    monkeypatch.setattr(base, "output", lambda cmd: "libavcodec62-32bit\n")
    base.packman_switch("packman")
    verbs = [c[2] for c in calls]
    assert verbs == ["--gpg-auto-import-keys", "dist-upgrade", "addlock",
                     "dist-upgrade", "removelock"]
    assert calls[2][3:] == ["libavcodec62-32bit"]


def test_packman_switch_fails_without_32bit(monkeypatch, tmp_path):
    monkeypatch.setattr(base, "ZYPP_LOCKS", tmp_path / "locks")
    monkeypatch.setattr(base, "run", lambda cmd, check=True: 0
                        if "refresh" in cmd else 4)
    monkeypatch.setattr(base, "output", lambda cmd: "bash\n")
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
    monkeypatch.setattr(base, "run", fake_run)
    monkeypatch.setattr(base, "output",
                        lambda cmd: "Mesa-32bit\nlibavcodec62-32bit\n")
    base.packman_switch("packman")
    assert calls[2][3:] == ["libavcodec62-32bit"]
    assert calls[4][3:] == ["libavcodec62-32bit"]


def test_packman_switch_fails_when_every_32bit_is_locked(monkeypatch,
                                                         tmp_path):
    locks = tmp_path / "locks"
    locks.write_text("solvable_name: Mesa-32bit\n")
    monkeypatch.setattr(base, "ZYPP_LOCKS", locks)
    monkeypatch.setattr(base, "run", lambda cmd, check=True: 0
                        if "refresh" in cmd else 4)
    monkeypatch.setattr(base, "output", lambda cmd: "Mesa-32bit\n")
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
    monkeypatch.setattr(base, "run", fake_run)
    monkeypatch.setattr(base, "output",
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
    assert verbs == ["addrepo", "--gpg-auto-import-keys", "dist-upgrade",
                     "install", "install"]
    assert fake_root.calls[3][-len(catalog.PACKMAN_CODECS):] == (
        catalog.PACKMAN_CODECS)


def test_codecs_install_removes_the_repo_it_added_on_failure(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path)
    fake_root.rc = {"dist-upgrade": 4}
    with pytest.raises(drivers.Fail):
        drivers.codecs_install([])
    assert fake_root.calls[-1][2:] == ["removerepo", catalog.PACKMAN_ALIAS]


def test_codecs_install_keeps_the_repo_when_packman_packages_are_in(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path)
    fake_root.rc = {"dist-upgrade": 4}
    fake_root.out = lambda cmd: PACKMAN_VENDOR if "%{VENDOR}\n" in cmd else ""
    with pytest.raises(drivers.Fail):
        drivers.codecs_install([])
    assert not any("removerepo" in c for c in fake_root.calls)


def test_codecs_install_never_removes_a_repo_that_was_there(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, True))
    fake_root.rc = {"dist-upgrade": 4}
    with pytest.raises(drivers.Fail):
        drivers.codecs_install([])
    assert not any(c[2] in ("addrepo", "removerepo", "modifyrepo")
                   for c in fake_root.calls)


def test_nvidia_install_removes_the_repo_it_added_on_failure(
        monkeypatch, fake_root):
    _repos(monkeypatch, [])
    fake_root.rc = {"install": 107}
    with pytest.raises(drivers.Fail):
        drivers.nvidia_install(["open"])
    assert fake_root.calls[-1][2:] == ["removerepo",
                                       catalog.NVIDIA_REPO_ALIAS]


def test_nvidia_install_keeps_the_repo_when_a_driver_is_in(
        monkeypatch, fake_root):
    _repos(monkeypatch, [])
    fake_root.rc = {"install": 107}
    fake_root.installed = {"nvidia-video-G07"}
    with pytest.raises(drivers.Fail):
        drivers.nvidia_install(["open"])
    assert not any("removerepo" in c for c in fake_root.calls)


def test_nvidia_install_never_removes_a_repo_that_was_there(
        monkeypatch, fake_root):
    _repos(monkeypatch, [("nvidia", NVIDIA_URL, True)])
    fake_root.rc = {"install": 107}
    with pytest.raises(drivers.Fail):
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
    with pytest.raises(drivers.Fail):
        drivers.codecs_install([])
    assert fake_root.calls[-1][2:] == ["modifyrepo", "--disable", "packman"]
    assert not any("removerepo" in c for c in fake_root.calls)


def test_codecs_install_disables_the_repo_even_with_packman_packages_in(
        monkeypatch, fake_root, tmp_path):
    _packman_env(monkeypatch, fake_root, tmp_path,
                 existing=("packman", PACKMAN_URL, False))
    fake_root.rc = {"dist-upgrade": 4}
    fake_root.out = lambda cmd: PACKMAN_VENDOR if "%{VENDOR}\n" in cmd else ""
    with pytest.raises(drivers.Fail):
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
    with pytest.raises(drivers.Fail):
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
    monkeypatch.setattr(repairs.os, "uname", lambda: types.SimpleNamespace(
        release="7.2.11-1-nazoos"))
    fake_root.installed = installed
    fake_root.out = lambda cmd: rpms
    repairs.repair_nvidia([])
    assert fake_root.calls[1] == repairs.ZYPPER_IN + ["--force", expected]


def test_repair_nvidia_without_driver(monkeypatch, fake_root):
    monkeypatch.setattr(repairs.os, "uname", lambda: types.SimpleNamespace(
        release="7.2.11-1-nazoos"))
    with pytest.raises(repairs.Fail):
        repairs.repair_nvidia([])


def test_channel_snapshots_before_the_link_changes(monkeypatch, fake_root,
                                                   tmp_path):
    link = tmp_path / "repoindex.xml"
    monkeypatch.setattr(catalog, "CHANNEL_LINK", str(link))
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
                     "--gpg-auto-import-keys", "dist-upgrade"]
    assert link_seen == [False, True, True, True]
    assert link.readlink().name == "nazoos-stable-repoindex.xml"
    assert fake_root.calls[-1][-3:-1] == ["--from", "nazoos:nazoos"]
