# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parts of the welcome root actions (nothing runs as root here)."""

import pytest

from nazoos_welcome import catalog
from nazoos_welcome.root import apps, base, drives, kernel_switch, tuning

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
    monkeypatch.setattr(ks.kernel, "ensure_grub_default", lambda say: True)
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
    monkeypatch.setattr(drives.system, "drives", lambda: [
        {"uuid": "abcd", "fstype": "ext4", "label": "Games",
         "managed": False}])
    monkeypatch.setattr(drives, "caller", lambda: (1000,))
    monkeypatch.setattr(drives, "output", lambda cmd: "100\n")
    monkeypatch.setattr(drives, "say", lambda *a: None)
    return fstab


def test_add_refuses_a_drive_the_gui_would_not_offer(monkeypatch, add_env):
    monkeypatch.setattr(drives.system, "drives", lambda: [])
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
    monkeypatch.setattr(tuning.system, "usb_input_devices",
                        lambda: [{"id": "046d:c08b"}])
    monkeypatch.setattr(tuning, "cmdline", lambda: (None, None, []))
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


def test_packman_switch_keeps_32bit_when_dup_fails(monkeypatch):
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


def test_packman_switch_fails_without_32bit(monkeypatch):
    monkeypatch.setattr(base, "run", lambda cmd, check=True: 0
                        if "refresh" in cmd else 4)
    monkeypatch.setattr(base, "output", lambda cmd: "bash\n")
    with pytest.raises(base.Fail):
        base.packman_switch("packman")
