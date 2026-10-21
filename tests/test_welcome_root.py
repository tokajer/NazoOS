# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parts of the welcome root actions (nothing runs as root here)."""

from nazoos_welcome import catalog
from nazoos_welcome.root import apps, drives, kernel_switch

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
