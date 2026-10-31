# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The way back to plain Tumbleweed (root/tumbleweed.py)."""

import ast
from pathlib import Path

import pytest

from nazoos_common import helper, kernel, kernelstate, proc, repos, zypper
from nazoos_welcome import catalog, system
from nazoos_welcome.root import apps, kernel_switch, tumbleweed

ROOT = Path(__file__).resolve().parent.parent
OSS = ("openSUSE:repo-oss", "http://cdn.opensuse.org/tumbleweed/repo/oss/", True)
OWN_CHANNEL = ("nazoos", "https://download.opensuse.org/repositories/home:/"
               "Tokajer:/nazoos:/release/openSUSE_Tumbleweed/", True)
OWN_KERNEL = ("nazoos-kernel", "https://download.opensuse.org/repositories/"
              "home:/Tokajer:/nazoos:/kernel/openSUSE_Tumbleweed/", True)
OWN_OFF = ("nazoos-old", "https://download.opensuse.org/repositories/home:/"
           "Tokajer:/nazoos:/devel/openSUSE_Tumbleweed/", False)
PACKMAN = ("packman", system.PACKMAN_URL, True)
VENDORS = {
    "nazoos-welcome": tumbleweed.OWN_VENDOR,
    "nazoos-tweaks": tumbleweed.OWN_VENDOR,
    "kernel-nazoos": tumbleweed.OWN_VENDOR,
    "xone": tumbleweed.OWN_VENDOR,
    "xone-kmp-nazoos": tumbleweed.OWN_VENDOR,
    "ffmpeg-7": "http://packman.links2linux.de",
    "sudo": "openSUSE",
    "gpg-pubkey": "(none)",
}


@pytest.fixture
def switch(fake_root, monkeypatch, tmp_path):
    """A NazoOS on the openSUSE kernel; every test sees the calls in order,
    with writes of the admin files as ["write", path]."""
    listed = [OSS, OWN_CHANNEL, OWN_KERNEL, OWN_OFF, PACKMAN]
    fake_root.listed = listed
    monkeypatch.setattr(repos, "repos", lambda: fake_root.listed)
    monkeypatch.setattr(repos, "with_path", lambda path: "openSUSE:repo-oss"
                        if path == tumbleweed.OSS_PATH else None)
    monkeypatch.setattr(kernel, "running_nazoos", lambda: False)
    fake_root.installed = {kernel.KERNEL_DEFAULT, "waydroid"}
    fake_root.out = lambda cmd: "".join(f"{n}\t{v}\n"
                                        for n, v in VENDORS.items())
    monkeypatch.setattr(zypper, "repo_search", lambda alias, name:
                        0 if name == "xone" else zypper.NOT_FOUND)
    monkeypatch.setattr(proc, "rc", lambda cmd, timeout=30: 0)
    monkeypatch.setattr(proc, "has", lambda tool: True)
    ctl = tmp_path / "session-ctl"
    ctl.touch()
    monkeypatch.setattr(system, "SESSION_CTL", str(ctl))
    monkeypatch.setattr(tumbleweed, "ADMIN_FILES", {
        tmp_path / "etc/sddm.conf.d/greeter.conf": "[General]\n",
        tmp_path / "etc/systemd/tty1.conf": "[Unit]\n"})
    monkeypatch.setattr(tumbleweed, "write_atomic", lambda path, text:
                        fake_root.calls.append(["write", str(path)]))
    monkeypatch.setattr(kernel_switch, "EFIVARS", str(tmp_path / "no-efivars"))
    (tmp_path / "grub-default").write_text('GRUB_TOP_LEVEL="/boot/x"\n')
    (tmp_path / "grub.cfg").touch()
    return fake_root


def dry_run(fake):
    return next(c for c in fake.calls if "--dry-run" in c)


def transaction(fake):
    return next(c for c in fake.calls if "install" in c and "--dry-run" not in c
                and "--force" not in c)


def index(fake, cmd):
    return next(i for i, c in enumerate(fake.calls) if c == cmd)


def position(fake, *words):
    return next(i for i, c in enumerate(fake.calls)
                if all(w in c for w in words))


def repo_calls(fake, verb):
    return [c[-1] for c in fake.calls if "modifyrepo" in c and verb in c]


def test_the_oss_path_is_the_one_repos_reads():
    assert repos.url_path(system.STANDARD_REPOS[0]["url"]) == tumbleweed.OSS_PATH


def test_stage_b_order(switch):
    tumbleweed.tumbleweed_switch([])
    fake = switch
    tx = fake.calls.index(transaction(fake))
    assert position(fake, "--disable", "nazoos") < position(fake, "snapper")
    assert position(fake, "snapper") < position(fake, "refresh", "openSUSE:repo-oss")
    assert position(fake, "refresh") < fake.calls.index(dry_run(fake))
    dry = fake.calls.index(dry_run(fake))
    for step in (position(fake, "boot-mode", "desktop"),
                 position(fake, "--remove-interface=waydroid0"),
                 position(fake, "firewall-cmd", "--set-default-zone=public"),
                 position(fake, "write")):
        assert dry < step < tx
    assert tx < position(fake, "--oldpackage")


def test_the_snapshot_can_be_named_by_nazoos_update(switch):
    tumbleweed.tumbleweed_switch([])
    assert "nazoos-welcome: before switching to Tumbleweed" in \
        switch.calls[position(switch, "snapper")]


def test_transaction_keeps_what_the_system_needs(switch):
    tumbleweed.tumbleweed_switch([])
    tx = transaction(switch)
    assert dry_run(switch) == tx[:4] + ["--dry-run"] + tx[4:]
    for package in ("sudo-policy-wheel-auth-self", "discover6-backend-packagekit",
                    "plasma6-branding-openSUSE", "plymouth-branding-openSUSE",
                    "grub2-branding-openSUSE"):
        assert package in tx
    assert not any("--clean-deps" in c for c in switch.calls)


def test_only_our_packages_without_a_twin_are_removed(switch):
    tumbleweed.tumbleweed_switch([])
    removed = [a[1:] for a in transaction(switch) if a.startswith("-")
               and not a.startswith("--")]
    assert removed == ["kernel-nazoos", "nazoos-tweaks", "nazoos-welcome",
                       "xone-kmp-nazoos"]


def test_packages_tumbleweed_has_too_change_to_its_build(switch):
    tumbleweed.tumbleweed_switch([])
    assert switch.calls[position(switch, "--oldpackage")][-4:] == [
        "--force", "--from", "openSUSE:repo-oss", "xone"]


def test_a_failed_package_search_stops_before_any_change(switch, monkeypatch):
    monkeypatch.setattr(zypper, "repo_search", lambda alias, name: 1)
    with pytest.raises(helper.Fail, match="zypper search"):
        tumbleweed.tumbleweed_switch([])
    assert not any("--dry-run" in c for c in switch.calls)
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]


def test_dead_repos_are_off_before_zypper_installs(switch):
    tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--disable") == ["nazoos", "nazoos-kernel"]
    assert position(switch, "--disable", "nazoos-kernel") < \
        switch.calls.index(dry_run(switch))
    # Past the point of no return they are not switched back on
    assert repo_calls(switch, "--enable") == []


def test_dry_run_failure_changes_nothing_and_restores_the_repos(switch):
    switch.rc = lambda cmd: 4 if "--dry-run" in cmd else 0
    with pytest.raises(helper.Fail) as e:
        tumbleweed.tumbleweed_switch([])
    assert e.value.params == {"rc": 4}
    assert "nothing was changed" in e.value.template
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]
    last = switch.calls.index(dry_run(switch))
    assert all("modifyrepo" in c for c in switch.calls[last + 1:])
    assert not any(c[0] in ("firewall-cmd", "write", "grub2-set-default")
                   or "boot-mode" in c for c in switch.calls)


def test_a_failing_preparation_restores_the_repos(switch):
    switch.rc = {"--set-default-zone=public": 252}
    with pytest.raises(helper.Fail):
        tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]
    assert not any("--force" in c or c[-1] == "-nazoos-welcome" and
                   "--dry-run" not in c for c in switch.calls)


def test_a_failure_while_disabling_restores_those_already_off(switch):
    switch.rc = lambda cmd: 1 if cmd[-1] == "nazoos-kernel" \
        and "--disable" in cmd else 0
    with pytest.raises(helper.Fail):
        tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--enable") == ["nazoos"]


def test_no_repo_oss_fails_clearly(switch, monkeypatch):
    monkeypatch.setattr(repos, "with_path", lambda path: None)
    with pytest.raises(helper.Fail, match="Tumbleweed repository is missing"):
        tumbleweed.tumbleweed_switch([])
    assert not any("snapper" in c for c in switch.calls)
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]


def transaction_ends_with(code):
    return lambda cmd: code if "-nazoos-welcome" in cmd \
        and "--dry-run" not in cmd else 0


def test_a_failed_transaction_points_at_the_snapshot_and_keeps_repos_off(switch):
    switch.rc = transaction_ends_with(8)
    with pytest.raises(helper.Fail, match="half-way.*snapshot"):
        tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--enable") == []
    assert not any("--oldpackage" in c for c in switch.calls)


def test_a_transaction_that_removed_a_part_counts_as_half_way(switch):
    switch.rc = transaction_ends_with(8)
    switch.installed |= {"nazoos-welcome", "kernel-nazoos", "xone-kmp-nazoos"}
    with pytest.raises(helper.Fail, match="half-way"):
        tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--enable") == []


def test_a_transaction_that_never_started_restores_the_repos(switch):
    switch.rc = transaction_ends_with(7)
    switch.installed |= {"nazoos-welcome", "nazoos-tweaks", "kernel-nazoos",
                         "xone-kmp-nazoos"}
    with pytest.raises(helper.Fail) as e:
        tumbleweed.tumbleweed_switch([])
    assert "were not changed" in e.value.template
    assert e.value.params == {"rc": 7}
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]
    assert not any("--oldpackage" in c or "removerepo" in c
                   for c in switch.calls)


def test_a_failed_rpm_script_counts_as_done(switch, monkeypatch, capsys):
    assert tumbleweed.RPM_SCRIPT_FAILED not in zypper.INFO
    switch.rc = transaction_ends_with(tumbleweed.RPM_SCRIPT_FAILED)
    said = []
    monkeypatch.setattr(tumbleweed, "say", said.append)
    tumbleweed.tumbleweed_switch([])
    assert any(s.startswith("Note: an RPM script") for s in said)
    assert position(switch, "--oldpackage")
    assert position(switch, "removerepo", "nazoos-kernel")
    assert repo_calls(switch, "--enable") == []
    assert "@@reboot" in capsys.readouterr().out


def test_grub_is_cleared_after_the_transaction(switch, tmp_path):
    tumbleweed.tumbleweed_switch([])
    tx = switch.calls.index(transaction(switch))
    cleared = position(switch, "grub2-set-default", "0")
    assert tx < cleared
    assert "GRUB_TOP_LEVEL" not in (tmp_path / "grub-default").read_text()
    # The rebuild for the removed kernel still follows
    assert any(c[0] == "grub2-mkconfig" for c in switch.calls[cleared:])


def test_a_failed_transaction_keeps_the_pin_of_stage_a(switch, tmp_path):
    switch.rc = transaction_ends_with(8)
    with pytest.raises(helper.Fail):
        tumbleweed.tumbleweed_switch([])
    assert not any(c[0] == "grub2-set-default" for c in switch.calls)
    assert "GRUB_TOP_LEVEL" in (tmp_path / "grub-default").read_text()


def test_without_top_level_the_saved_default_stays(switch, tmp_path):
    (tmp_path / "grub-default").write_text("GRUB_DEFAULT=saved\n")
    tumbleweed.tumbleweed_switch([])
    assert not any(c[0] == "grub2-set-default" for c in switch.calls)
    assert any(c[0] == "grub2-mkconfig" for c in switch.calls)


def test_a_failure_while_clearing_grub_is_only_a_note(switch, monkeypatch,
                                                      capsys):
    switch.rc = {"grub2-set-default": 1}
    said = []
    monkeypatch.setattr(tumbleweed, "say", said.append)
    tumbleweed.tumbleweed_switch([])
    assert any(s.startswith("Note: the boot menu default") for s in said)
    assert any(c[0] == "grub2-mkconfig" for c in switch.calls)
    assert "@@reboot" in capsys.readouterr().out


def test_an_unreadable_grub_file_is_only_a_note(switch, monkeypatch, tmp_path):
    (tmp_path / "grub-default").unlink()
    said = []
    monkeypatch.setattr(tumbleweed, "say", said.append)
    tumbleweed.tumbleweed_switch([])
    assert any(s.startswith("Note: the boot menu default") for s in said)


def test_clean_up_failure_does_not_fail_the_action(switch, monkeypatch, capsys):
    def rc(cmd):
        # Everything after the real transaction fails
        return 1 if any("-nazoos-welcome" in c and "--dry-run" not in c
                        for c in switch.calls[:-1]) else 0
    switch.rc = rc
    said = []
    monkeypatch.setattr(tumbleweed, "say", said.append)
    tumbleweed.tumbleweed_switch([])
    notes = [s for s in said if s.startswith("Note: ")]
    # Forced install, lock, boot default, boot menu, three repos, key
    assert len(notes) == 8
    assert "@@reboot" in capsys.readouterr().out


def test_clean_up_removes_our_repos_lock_and_key(switch, capsys):
    tumbleweed.tumbleweed_switch([])
    removed = [c[-1] for c in switch.calls if "removerepo" in c]
    assert removed == ["nazoos", "nazoos-kernel", "nazoos-old"]
    assert not any("packman" in c and "removerepo" in c for c in switch.calls)
    assert switch.calls[position(switch, "removelock")][-1] == "plasma6-session-x11"
    assert ["rpm", "-e", "--allmatches", "gpg-pubkey-a686e7d6"] in switch.calls
    assert "@@reboot" in capsys.readouterr().out


def test_waydroid_cleanup_only_with_waydroid(switch):
    switch.installed = {kernel.KERNEL_DEFAULT}
    tumbleweed.tumbleweed_switch([])
    assert not any("--remove-interface=waydroid0" in c for c in switch.calls)


def test_waydroid_cleanup_uses_the_catalog_interfaces(switch, monkeypatch):
    seen = []
    monkeypatch.setattr(apps, "firewall_zone", lambda *a: seen.append(a))
    tumbleweed.tumbleweed_switch([])
    assert seen == [(catalog.by_id(catalog.APPS, "waydroid")["firewall"], False)]


def test_firewall_without_a_running_firewalld(switch, monkeypatch):
    monkeypatch.setattr(proc, "rc", lambda cmd, timeout=30: 3)
    tumbleweed.tumbleweed_switch([])
    assert ["firewall-offline-cmd", "--set-default-zone=public"] in switch.calls
    assert not any(c[0] == "firewall-cmd" for c in switch.calls)


def test_never_the_permanent_flag_next_to_the_default_zone(switch):
    # firewall-cmd: "Can't use stand-alone options with other options"
    tumbleweed.tumbleweed_switch([])
    assert not any("--permanent" in c and "--set-default-zone=public" in c
                   for c in switch.calls)


def test_no_gaming_mode_tool_no_boot_mode_step(switch, monkeypatch, tmp_path):
    monkeypatch.setattr(system, "SESSION_CTL", str(tmp_path / "gone"))
    tumbleweed.tumbleweed_switch([])
    assert not any("boot-mode" in c for c in switch.calls)


def test_login_screen_files_match_what_nazoos_tweaks_ships():
    tweaks = ROOT / "packages/nazoos-tweaks"
    files = {p.name: text for p, text in tumbleweed.ADMIN_FILES.items()}
    assert all(p.parent.is_absolute() and str(p).startswith("/etc/")
               for p in tumbleweed.ADMIN_FILES)

    def settings(path):
        return [line for line in path.read_text().splitlines()
                if line and not line.startswith("#")]

    assert files["10-wayland-greeter.conf"].splitlines() == settings(
        tweaks / "sddm/10-nazoos-wayland.conf")
    assert files["10-wayland-tty1.conf"].splitlines() == settings(
        tweaks / "systemd/display-manager-legacy.service.d/10-nazoos-tty1.conf")
    assert files["50-nvidia-wayland.conf"].strip() in settings(
        tweaks / "modprobe.d/nvidia.conf")


@pytest.mark.parametrize("running,default", [(True, True), (True, False),
                                             (False, False)])
def test_stage_a_only_moves_to_the_openSUSE_kernel(switch, monkeypatch, capsys,
                                                   running, default):
    monkeypatch.setattr(kernel, "running_nazoos", lambda: running)
    monkeypatch.setattr(kernelstate, "PREFER", Path("/nonexistent/prefer"))
    monkeypatch.setattr(kernel_switch.grub, "ensure_grub_default",
                        lambda say, flavor: True)
    switch.installed = {"waydroid"} | ({kernel.KERNEL_DEFAULT} if default else set())
    tumbleweed.tumbleweed_switch([])
    # Only kernel_restore's install, with the dead repos off for it
    installs = [c for c in switch.calls if "install" in c]
    assert installs == [zypper.ZYPPER_IN + [kernel.KERNEL_DEFAULT]]
    assert position(switch, "--disable", "nazoos-kernel") < switch.calls.index(
        installs[0])
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]
    assert switch.calls.index(installs[0]) < position(switch, "--enable")
    assert not any(c[0] in ("snapper", "firewall-cmd", "write") or "boot-mode" in c
                   or "removerepo" in c for c in switch.calls)
    out = capsys.readouterr().out
    assert "again" in out and "@@reboot" in out


def test_stage_a_failure_restores_the_repos(switch, monkeypatch):
    monkeypatch.setattr(kernel, "running_nazoos", lambda: True)
    switch.rc = {"install": 4}
    with pytest.raises(helper.Fail):
        tumbleweed.tumbleweed_switch([])
    assert repo_calls(switch, "--enable") == ["nazoos", "nazoos-kernel"]


def test_nothing_is_imported_after_the_transaction():
    """The transaction deletes these modules while they run."""
    paths = [ROOT / "packages/nazoos-welcome/nazoos_welcome/root/tumbleweed.py",
             *(ROOT / "packages/nazoos-common/nazoos_common").glob("*.py")]
    for path in paths:
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(isinstance(n, (ast.Import, ast.ImportFrom))
                               for n in ast.walk(fn)), f"{path}: {fn.name}"
