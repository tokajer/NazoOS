# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The move from Tumbleweed to Slowroll (root/slowroll.py)."""

import ast
from pathlib import Path

import pytest

from nazoos_common import helper, repos, zypper
from nazoos_welcome import system
from nazoos_welcome.root import kernel_switch, slowroll, tumbleweed

ROOT = Path(__file__).resolve().parent.parent
OBS = "https://download.opensuse.org/repositories/home:/Tokajer:/nazoos:/"
TW_REPOS = [
    ("openSUSE:repo-oss", "http://cdn.opensuse.org/tumbleweed/repo/oss/", True),
    ("nazoos:nazoos", OBS + "release/openSUSE_Tumbleweed/", True),
]
SR_REPOS = [
    ("openSUSE:repo-oss", "http://cdn.opensuse.org/slowroll/repo/oss/", True),
    ("nazoos:nazoos", OBS + "release/openSUSE_Slowroll/", True),
]
PLAIN = [
    ("packman", "https://ftp.fau.de/packman/suse/openSUSE_Tumbleweed/", True),
    ("nazoos-kernel", OBS + "kernel/openSUSE_Tumbleweed/", True),
    ("NVIDIA", "https://download.nvidia.com/opensuse/tumbleweed", True),
]
OPTIONS = {
    "packman": {"name": "Packman", "priority": "70", "enabled": "1",
                "autorefresh": "1", "gpgcheck": "1"},
    "nazoos-kernel": {"name": "nazoos-kernel", "priority": "90",
                      "enabled": "1", "autorefresh": "1"},
}
OWN = ["kernel-nazoos", "nazoos-common", "nazoos-tweaks", "nazoos-welcome",
       "xone", "xone-kmp-nazoos"]
IN_REPO = {"nazoos:nazoos": {"nazoos-common", "nazoos-tweaks",
                             "nazoos-welcome"},
           "nazoos-kernel": {"kernel-nazoos", "xone", "xone-kmp-nazoos"}}


class System:
    """zypper and rpm of a NazoOS on Tumbleweed: the repo package swap
    changes the service repos, removerepo/addrepo the plain ones."""

    def __init__(self, fake):
        self.fake = fake
        self.service = list(TW_REPOS)
        self.plain = list(PLAIN)
        self.options = {k: dict(v) for k, v in OPTIONS.items()}
        # Exit codes by words of the command, and whether the swap works
        self.codes = {}
        self.swap_lists_repos = True
        self.dup_changes = True
        self.rpm_db = "a-1-1.x86_64\n"
        self.own = list(OWN)
        self.in_repo = {k: set(v) for k, v in IN_REPO.items()}
        fake.installed = {"openSUSE-repos-Tumbleweed"}

    def repos(self):
        return self.service + self.plain

    def run(self, cmd):
        for words, code in self.codes.items():
            if all(w in cmd for w in words):
                return code
        if "--plus-repo" in cmd:
            target = ("slowroll" if "openSUSE-repos-Slowroll" in cmd
                      else "tumbleweed")
            self.fake.installed = {repos.BASE_PACKAGES[target]}
            if self.swap_lists_repos:
                # The service refresh keeps the state of an alias it knows
                off = {a for a, _u, on in self.service if not on}
                self.service = [(a, u, on and a not in off) for a, u, on in
                                (SR_REPOS if target == "slowroll"
                                 else TW_REPOS)]
        elif "modifyrepo" in cmd:
            self.service = [(a, u, "--enable" in cmd if a == cmd[-1] else on)
                            for a, u, on in self.service]
        elif "removerepo" in cmd:
            self.plain = [r for r in self.plain if r[0] != cmd[-1]]
        elif "addrepo" in cmd:
            self.plain.append((cmd[-1], cmd[-2], "--disable" not in cmd))
        elif ("dist-upgrade" in cmd and "--dry-run" not in cmd
              and self.dup_changes):
            self.rpm_db = "a-2-1.x86_64\n"
        return 0

    def output(self, cmd):
        if "%{NAME}\t%{VENDOR}\n" in cmd:
            return "".join(f"{n}\t{tumbleweed.OWN_VENDOR}\n" for n in self.own) \
                + "sudo\topenSUSE\n"
        return self.rpm_db


@pytest.fixture
def sr(fake_root, monkeypatch, tmp_path):
    state = System(fake_root)
    fake_root.rc = state.run
    fake_root.out = state.output
    monkeypatch.setattr(repos, "repos", state.repos)
    monkeypatch.setattr(repos, "options",
                        lambda alias: state.options.get(alias, {}))
    link = tmp_path / "repoindex.xml"
    link.symlink_to("nazoos-stable-repoindex.xml")
    monkeypatch.setattr(system, "CHANNEL_LINK", str(link))
    monkeypatch.setattr(zypper, "repo_search", lambda alias, name:
                        0 if name in state.in_repo.get(alias, ()) else
                        zypper.NOT_FOUND)
    monkeypatch.setattr(slowroll, "wait_for_lock", lambda: True)
    monkeypatch.setattr(kernel_switch, "EFIVARS", str(tmp_path / "no-efivars"))
    return state


def calls(state, *words):
    return [c for c in state.fake.calls if all(w in c for w in words)]


def position(state, *words):
    return next(i for i, c in enumerate(state.fake.calls)
                if all(w in c for w in words))


def swaps(state):
    return calls(state, "--plus-repo")


def test_refuses_on_slowroll(sr):
    sr.fake.installed = {"openSUSE-repos-Slowroll"}
    with pytest.raises(helper.Fail, match="already runs on openSUSE Slowroll"):
        slowroll.slowroll_switch([])
    assert sr.fake.calls == []


def test_a_held_zypp_lock_stops_before_any_change(sr, monkeypatch):
    monkeypatch.setattr(slowroll, "wait_for_lock", lambda: False)
    with pytest.raises(helper.Fail, match="changing software"):
        slowroll.slowroll_switch([])
    assert sr.fake.calls == []


def test_without_a_channel_nothing_happens(sr, monkeypatch, tmp_path):
    monkeypatch.setattr(system, "CHANNEL_LINK", str(tmp_path / "gone"))
    with pytest.raises(helper.Fail, match="Repair page"):
        slowroll.slowroll_switch([])
    assert sr.fake.calls == []


def test_happy_path_order(sr, capsys):
    slowroll.slowroll_switch([])
    verbs = [c[2] if c[0] == "zypper" and c[2] != "--plus-repo" else
             "swap" if "--plus-repo" in c else c[0] for c in sr.fake.calls]
    assert verbs == ["snapper", "modifyrepo", "swap", "refresh-services",
                     "modifyrepo", "removerepo", "addrepo", "removerepo",
                     "addrepo", "dist-upgrade", "dist-upgrade", "install"]
    assert "nazoos-welcome: before switching to Slowroll" in sr.fake.calls[0]
    out = capsys.readouterr().out
    assert "@@reboot" in out and "runs on openSUSE Slowroll" in out


def test_repo_packages_come_from_the_slowroll_seeds_of_the_channel(sr):
    slowroll.slowroll_switch([])
    swap = swaps(sr)[0]
    seeds = [swap[i + 1] for i, a in enumerate(swap) if a == "--plus-repo"]
    assert seeds == ["https://download.opensuse.org/slowroll/repo/oss/",
                     OBS + "release/openSUSE_Slowroll/"]
    assert swap[-4:] == ["--force", "--auto-agree-with-licenses",
                         "openSUSE-repos-Slowroll", "nazoos-repos"]


def test_the_beta_channel_seeds_the_devel_repo(sr, tmp_path):
    link = tmp_path / "repoindex.xml"
    link.unlink()
    link.symlink_to("nazoos-beta-repoindex.xml")
    sr.service = [TW_REPOS[0], ("nazoos:nazoos-devel",
                                OBS + "devel/openSUSE_Tumbleweed/", True)]
    sr.swap_lists_repos = False

    def swap(cmd):
        if "--plus-repo" in cmd and "openSUSE-repos-Slowroll" in cmd:
            sr.fake.installed = {"openSUSE-repos-Slowroll"}
            sr.service = [SR_REPOS[0], ("nazoos:nazoos-devel",
                                        OBS + "devel/openSUSE_Slowroll/", True)]
            return 0
        return System.run(sr, cmd)
    sr.fake.rc = swap
    sr.in_repo["nazoos:nazoos-devel"] = sr.in_repo["nazoos:nazoos"]
    slowroll.slowroll_switch([])
    assert OBS + "devel/openSUSE_Slowroll/" in swaps(sr)[0]
    assert calls(sr, "--oldpackage")[0][-5:-3] == ["--from",
                                                   "nazoos:nazoos-devel"]


def test_packman_and_kernel_repo_move_with_their_settings(sr):
    sr.options["packman"]["enabled"] = "0"
    slowroll.slowroll_switch([])
    adds = {c[-1]: c for c in calls(sr, "addrepo")}
    assert set(adds) == {"packman", "nazoos-kernel"}
    pm, k = adds["packman"], adds["nazoos-kernel"]
    assert pm[-2] == "https://ftp.fau.de/packman/suse/openSUSE_Slowroll/"
    assert pm[pm.index("--priority") + 1] == "70"
    assert pm[pm.index("--name") + 1] == "Packman"
    assert "--disable" in pm and "--refresh" in pm
    assert k[-2] == OBS + "kernel/openSUSE_Slowroll/"
    assert k[k.index("--priority") + 1] == "90" and "--disable" not in k
    # Each one is removed right before it is added again
    for alias in adds:
        assert position(sr, "removerepo", alias) + 1 == position(
            sr, "addrepo", alias)
    assert not calls(sr, "NVIDIA")
    assert ("NVIDIA", "https://download.nvidia.com/opensuse/tumbleweed",
            True) in sr.plain


def test_a_packman_mirror_stays_the_same_mirror(sr):
    sr.plain[0] = ("packman", "https://ftp.gwdg.de/pub/linux/misc/packman/"
                   "suse/openSUSE_Tumbleweed/", True)
    slowroll.slowroll_switch([])
    assert calls(sr, "addrepo", "packman")[0][-2] == (
        "https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Slowroll/")


def test_the_dry_run_keeps_vendors_and_comes_before_the_upgrade(sr):
    slowroll.slowroll_switch([])
    dry, real = calls(sr, "dist-upgrade")
    assert "--dry-run" in dry and "--dry-run" not in real
    for cmd in (dry, real):
        assert not {"--allow-vendor-change", "--force-resolution"} & set(cmd)
    assert position(sr, "addrepo", "nazoos-kernel") < position(sr, "--dry-run")


def undone(state):
    """The repo package swap back to Tumbleweed and the plain repos back
    on their Tumbleweed URLs."""
    back = [c for c in swaps(state) if "openSUSE-repos-Tumbleweed" in c]
    return back, state.plain


def test_dry_run_failure_undoes_the_swap_and_changes_nothing(sr):
    sr.codes = {("dist-upgrade", "--dry-run"): 4}
    with pytest.raises(helper.Fail) as e:
        slowroll.slowroll_switch([])
    assert "nothing was changed" in e.value.template
    assert e.value.params == {"rc": 4}
    back, plain = undone(sr)
    assert len(back) == 1
    seeds = [back[0][i + 1] for i, a in enumerate(back[0]) if a == "--plus-repo"]
    assert seeds == ["https://download.opensuse.org/tumbleweed/repo/oss/",
                     OBS + "release/openSUSE_Tumbleweed/"]
    assert sorted(plain) == sorted(PLAIN)
    assert sr.service == TW_REPOS
    assert sr.fake.installed == {"openSUSE-repos-Tumbleweed"}
    assert len(calls(sr, "dist-upgrade")) == 1
    assert not calls(sr, "--oldpackage")


def test_missing_slowroll_repos_after_the_swap_roll_back(sr):
    sr.swap_lists_repos = False
    with pytest.raises(helper.Fail, match="did not appear; nothing was changed"):
        slowroll.slowroll_switch([])
    back, _plain = undone(sr)
    assert len(back) == 1
    assert sr.fake.installed == {"openSUSE-repos-Tumbleweed"}
    assert not calls(sr, "removerepo") and not calls(sr, "dist-upgrade")


def test_a_failed_swap_install_needs_no_swap_back(sr):
    sr.codes = {("--plus-repo",): 8}
    with pytest.raises(helper.Fail, match="failed"):
        slowroll.slowroll_switch([])
    assert len(swaps(sr)) == 1
    assert not calls(sr, "refresh-services")


def test_a_failed_undo_points_at_the_snapshot(sr):
    sr.codes = {("dist-upgrade", "--dry-run"): 4,
                ("--plus-repo", "openSUSE-repos-Tumbleweed"): 8}
    with pytest.raises(helper.Fail, match="could not be restored.*snapshot"):
        slowroll.slowroll_switch([])


def test_an_upgrade_that_never_started_undoes_the_swap(sr):
    def rc(cmd):
        if "dist-upgrade" in cmd and "--dry-run" not in cmd:
            return 8
        return System.run(sr, cmd)
    sr.fake.rc = rc
    with pytest.raises(helper.Fail) as e:
        slowroll.slowroll_switch([])
    assert "did not start" in e.value.template
    assert len(undone(sr)[0]) == 1
    assert sorted(sr.plain) == sorted(PLAIN)


def test_an_upgrade_that_stopped_half_way_keeps_slowroll(sr):
    def rc(cmd):
        if "dist-upgrade" in cmd and "--dry-run" not in cmd:
            sr.rpm_db = "a-2-1.x86_64\n"
            return 8
        return System.run(sr, cmd)
    sr.fake.rc = rc
    with pytest.raises(helper.Fail, match="half-way.*snapshot"):
        slowroll.slowroll_switch([])
    assert not undone(sr)[0]
    assert not calls(sr, "--oldpackage")


def test_a_failed_rpm_script_counts_as_done(sr, capsys):
    def rc(cmd):
        if "dist-upgrade" in cmd and "--dry-run" not in cmd:
            return tumbleweed.RPM_SCRIPT_FAILED
        return System.run(sr, cmd)
    sr.fake.rc = rc
    slowroll.slowroll_switch([])
    assert calls(sr, "--oldpackage")
    assert "@@reboot" in capsys.readouterr().out


def test_our_packages_change_to_the_slowroll_build_but_not_the_kernel(sr):
    slowroll.slowroll_switch([])
    (reinstall,) = calls(sr, "--oldpackage")
    assert reinstall[-6:] == ["--force", "--from", "nazoos:nazoos",
                              "nazoos-common", "nazoos-tweaks",
                              "nazoos-welcome"]
    assert reinstall.index("--oldpackage") > reinstall.index("install")
    # Never the files of the running kernel, also not what only the kernel
    # repo has
    assert not {"kernel-nazoos", "xone-kmp-nazoos", "xone"} & set(reinstall)
    assert position(sr, "dist-upgrade") < position(sr, "--oldpackage")


def test_kernel_repo_packages_stay_even_without_a_name_hint(sr):
    sr.own.append("xpadneo")
    sr.in_repo["nazoos:nazoos"].add("xpadneo")
    sr.in_repo["nazoos-kernel"].add("xpadneo")
    slowroll.slowroll_switch([])
    assert "xpadneo" not in calls(sr, "--oldpackage")[0]


def test_a_failed_reinstall_is_only_a_note(sr, monkeypatch, capsys):
    sr.codes = {("--oldpackage",): 8}
    said = []
    monkeypatch.setattr(slowroll, "say", said.append)
    slowroll.slowroll_switch([])
    assert any(s.startswith("Note: some packages still are the Tumbleweed")
               for s in said)
    assert "@@reboot" in capsys.readouterr().out


def test_the_snapshot_comes_first(sr):
    slowroll.slowroll_switch([])
    assert sr.fake.calls[0][0] == "snapper"


def test_the_snapshot_can_be_named_by_nazoos_update():
    from nazoos_update.root import snapshots
    from nazoos_welcome.root import maintenance

    description = maintenance.CHANNEL_SNAPSHOT.format(
        target=system.base_name(slowroll.TO))
    assert snapshots.snapshot_label(
        {"number": 7, "type": "single", "description": description},
        set(), False, lambda s: s) == "Before channel switch"


def test_nothing_is_imported_inside_a_function():
    """The forced reinstall replaces this module while it runs."""
    path = ROOT / "packages/nazoos-welcome/nazoos_welcome/root/slowroll.py"
    tree = ast.parse(path.read_text())
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert not any(isinstance(n, (ast.Import, ast.ImportFrom))
                           for n in ast.walk(fn)), fn.name


def test_the_old_channel_repo_is_off_for_the_swap_and_the_new_one_on(sr):
    slowroll.slowroll_switch([])
    zypper = [c[2:] for c in sr.fake.calls[1:5]]
    assert zypper[0] == ["modifyrepo", "--disable", "nazoos:nazoos"]
    assert "--plus-repo" in zypper[1] and "openSUSE-repos-Slowroll" in zypper[1]
    assert zypper[2] == ["refresh-services"]
    assert zypper[3] == ["modifyrepo", "--enable", "nazoos:nazoos"]
    # The Slowroll repo would stay off without the explicit enable
    assert ("nazoos:nazoos", OBS + "release/openSUSE_Slowroll/", True) \
        in sr.service


def test_a_failed_swap_install_switches_the_old_channel_repo_on_again(sr):
    sr.codes = {("--plus-repo",): 8}
    with pytest.raises(helper.Fail):
        slowroll.slowroll_switch([])
    assert calls(sr, "modifyrepo")[-1][2:] == ["modifyrepo", "--enable",
                                                "nazoos:nazoos"]
    assert sr.service == TW_REPOS


def test_the_way_back_also_swaps_the_channel_repos(sr):
    sr.codes = {("dist-upgrade", "--dry-run"): 4}
    with pytest.raises(helper.Fail):
        slowroll.slowroll_switch([])
    back = sr.fake.calls.index(undone(sr)[0][0])
    assert sr.fake.calls[back - 1][2:] == ["modifyrepo", "--disable",
                                           "nazoos:nazoos"]
    assert sr.fake.calls[back + 2][2:] == ["modifyrepo", "--enable",
                                           "nazoos:nazoos"]
    assert sr.service == TW_REPOS


def test_a_half_moved_repo_comes_back_with_its_settings(sr):
    # removerepo worked, addrepo did not: the repo is gone until the undo
    def rc(cmd):
        if "addrepo" in cmd and "openSUSE_Slowroll" in cmd[-2]:
            return 4
        return System.run(sr, cmd)
    sr.fake.rc = rc
    with pytest.raises(helper.Fail):
        slowroll.slowroll_switch([])
    # The first plain repo (packman) failed: only it is put back
    readd = calls(sr, "addrepo")[-1]
    assert readd[-2:] == [PLAIN[0][1], "packman"]
    assert readd[readd.index("--priority") + 1] == "70"
    assert readd[readd.index("--name") + 1] == "Packman"
    assert ("packman", PLAIN[0][1], True) in sr.plain
    assert not calls(sr, "addrepo", "nazoos-kernel")
    assert len(undone(sr)[0]) == 1


def test_undo_runs_every_step_and_fails_once(sr, monkeypatch):
    said = []
    monkeypatch.setattr(slowroll, "say", said.append)

    def rc(cmd):
        if "--dry-run" in cmd:
            return 4
        # The first restore step: the kernel repo back on Tumbleweed
        if "addrepo" in cmd and cmd[-1] == "nazoos-kernel" \
                and "openSUSE_Tumbleweed" in cmd[-2]:
            return 4
        return System.run(sr, cmd)
    sr.fake.rc = rc
    with pytest.raises(helper.Fail, match="could not be restored") as e:
        slowroll.slowroll_switch([])
    assert isinstance(e.value.__cause__, helper.Fail)
    # Packman and the repo packages are still restored after it
    assert ("packman", PLAIN[0][1], True) in sr.plain
    assert len(undone(sr)[0]) == 1
    assert sr.fake.installed == {"openSUSE-repos-Tumbleweed"}
    assert sum(s.startswith("Note: ") for s in said) == 1
