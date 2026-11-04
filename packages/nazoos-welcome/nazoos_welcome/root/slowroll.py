# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Switch to Slowroll: moves a NazoOS on Tumbleweed to openSUSE Slowroll,
the base NazoOS is built for now (docs/update.md).

Not opensuse-migration-tool: it switches off every repo that is not
openSUSE's (our service "nazoos" too), and its "dup --allow-vendor-change"
would swap our packages for openSUSE's builds.

The transaction replaces this code under the running helper: everything
used after it has to be imported here at the top, never inside a function.
"""

from nazoos_common import helper, kernel, proc, repos
from nazoos_common.helper import Fail, say
from nazoos_common.zypper import OK, ZYPPER, ZYPPER_IN, wait_for_lock

from .. import system
from . import kernel_switch, maintenance, tumbleweed

FROM, TO = "tumbleweed", "slowroll"
DOWNLOAD = "https://download.opensuse.org"


def _swap_repo_packages(base, channel):
    """openSUSE-repos-<Base> and the nazoos-repos build for BASE in one
    transaction, both from seed repos (the service repos of BASE are not
    there yet), then the services list the repos of BASE."""
    old = repos.with_path(
        system.channel_repo_paths(TO if base == FROM else FROM)[channel])
    # The installed nazoos-repos is also in our old channel repo, priority
    # 90 beats the seeds' 99 and the solver may stick to it: off for the
    # install
    if old is not None:
        helper.run(ZYPPER + ["modifyrepo", "--disable", old])
    # --force: both builds of nazoos-repos have the same version-release.
    # Only the build for BASE can stay next to openSUSE-repos-<Base>
    # (Requires, and the openSUSE-repos packages conflict), so the solver
    # cannot keep the old one
    try:
        helper.run(ZYPPER + [
            "--plus-repo", system.oss_url(base),
            "--plus-repo", DOWNLOAD + system.channel_repo_paths(base)[channel],
            "install", "--force", "--auto-agree-with-licenses",
            repos.BASE_PACKAGES[base], "nazoos-repos"])
    except Exception:
        if old is not None:
            helper.run(ZYPPER + ["modifyrepo", "--enable", old], check=False)
        raise
    helper.run(ZYPPER + ["refresh-services"])
    # Both builds name the repo alike (nazoos, nazoos-devel): the service
    # refresh keeps the disabled state of the same alias
    new = repos.with_path(system.channel_repo_paths(base)[channel])
    if new is not None:
        helper.run(ZYPPER + ["modifyrepo", "--enable", new])


def _swapped(channel):
    """The services list Slowroll's repo-oss and our Slowroll repo."""
    return (repos.with_path(repos.url_path(system.oss_url(TO))) is not None
            and repos.with_path(system.channel_repo_paths(TO)[channel])
            is not None)


def _base_repos():
    """(alias, URL) of the plain repos whose URL names Tumbleweed and that
    have a Slowroll build: Packman and the NazoOS kernel. NVIDIA has no
    Slowroll repo and stays."""
    kernel_alias = kernel.kernel_repo()
    old = f"/{repos.OBS_REPOS[FROM]}/"
    return [(alias, url) for alias, url, _on in repos.repos()
            if old in url and ("/packman/" in url or alias == kernel_alias)]


def _move_repo(alias, url, opts):
    """Point repo ALIAS at URL. zypper cannot change a URL in place: the
    repo is added again with the name, priority, enabled, refresh and
    signature check settings OPTS (repos.options(), read before the first
    move). Its key stays imported (same key for both bases)."""
    args = ["--name", opts.get("name", alias).strip()]
    if "priority" in opts:
        args += ["--priority", opts["priority"].strip()]
    if not repos.flag(opts, "enabled", "1"):
        args.append("--disable")
    if repos.flag(opts, "autorefresh", "0"):
        args.append("--refresh")
    if not repos.flag(opts, "gpgcheck", "1"):
        args.append("--no-gpgcheck")
    # Gone already (an earlier half move): fine. Still there: addrepo fails
    helper.run(ZYPPER + ["removerepo", alias], check=False)
    helper.run(ZYPPER + ["addrepo"] + args + [url, alias])


def _undo(channel, moved):
    """Back to the Tumbleweed repos after a failure before the upgrade.
    Every step is tried: one that fails must not leave the rest moved."""
    steps = [lambda a=alias, u=url, o=opts: _move_repo(a, u, o)
             for alias, url, opts in reversed(moved)]
    if proc.rpm_installed(repos.BASE_PACKAGES[TO]):
        steps.append(lambda: _swap_repo_packages(FROM, channel))
    errors = []
    for step in steps:
        try:
            step()
        except (Fail, OSError) as e:
            say(f"Note: {e}")
            errors.append(e)
    if errors:
        raise Fail("the switch to Slowroll failed and the Tumbleweed "
                   "repositories could not be restored (details in the "
                   "log); restart and go back to the snapshot in the boot "
                   "menu") from errors[0]


def _installed():
    return sorted(helper.output(
        ["rpm", "-qa", "--qf",
         "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n"]).splitlines())


def _kernel_package(name, kernel_alias):
    return (name.startswith("kernel-") or "-kmp-" in name
            or (kernel_alias is not None
                and kernel_switch.in_repo(kernel_alias, name)))


def _reinstall_own(channel):
    """Our packages have the same version-release in both OBS repos, so
    dup kept the Tumbleweed builds: install the Slowroll ones. The system
    runs on Slowroll already, a failure is only worth a note."""
    alias = repos.with_path(system.channel_repo_paths(TO)[channel])
    try:
        kernel_alias = kernel.kernel_repo()
        # Never the kernel repo's packages (kernel-nazoos, its modules,
        # kernel-syms): the files of the running kernel must not be
        # replaced. The Tumbleweed build keeps working on Slowroll and the
        # next kernel update brings the Slowroll one
        names = [n for n in tumbleweed.own_packages()
                 if alias is not None and kernel_switch.in_repo(alias, n)
                 and not _kernel_package(n, kernel_alias)]
    except (Fail, OSError) as e:
        say(f"Note: the NazoOS packages could not be checked: {e}")
        return
    if names and helper.run(ZYPPER_IN + ["--oldpackage", "--force", "--from",
                                         alias] + names, check=False):
        say("Note: some packages still are the Tumbleweed build: "
            + " ".join(names))


def slowroll_switch(_args):
    if repos.base() != FROM:
        raise Fail("this system already runs on openSUSE Slowroll")
    # Before anything: removerepo and refresh would hang on a held lock
    if not wait_for_lock():
        raise Fail("another program is changing software right now; close "
                   "it and try again")
    channel = system.current_channel()
    if not channel:
        raise Fail("the NazoOS repositories are not set up; repair them on "
                   "the Repair page first")
    maintenance.create_snapshot(maintenance.CHANNEL_SNAPSHOT.format(
        target=system.base_name(TO)))
    moved = []
    try:
        _swap_repo_packages(TO, channel)
        if not _swapped(channel):
            raise Fail("the Slowroll repositories did not appear; nothing "
                       "was changed")
        new = f"/{repos.OBS_REPOS[TO]}/"
        for alias, url in _base_repos():
            opts = repos.options(alias)
            # Recorded first: a failed addrepo after removerepo is undone too
            moved.append((alias, url, opts))
            _move_repo(alias, url.replace(f"/{repos.OBS_REPOS[FROM]}/", new),
                       opts)
        # No --allow-vendor-change: our packages and Packman's stay theirs
        rc = helper.run(ZYPPER + ["dist-upgrade", "--dry-run",
                                  "--auto-agree-with-licenses"], check=False)
        if rc not in OK:
            raise Fail("the switch to Slowroll is not possible right now "
                       "(zypper exit code {rc}, details in the log); "
                       "nothing was changed", rc=rc)
    except Exception:
        _undo(channel, moved)
        raise
    before = _installed()
    with kernel_switch.efivars_read_only():
        rc = helper.run(ZYPPER + ["dist-upgrade",
                                  "--auto-agree-with-licenses"], check=False)
    if rc == tumbleweed.RPM_SCRIPT_FAILED:
        say("Note: an RPM script failed, the packages are changed anyway")
    elif rc:
        # zypper never started (its lock, a download): no package changed
        if _installed() == before:
            _undo(channel, moved)
            raise Fail("the switch to Slowroll did not start (zypper exit "
                       "code {rc}, details in the log); nothing was "
                       "changed, try again later", rc=rc)
        # Point of no return: half Tumbleweed, half Slowroll
        raise Fail("the switch to Slowroll stopped half-way (zypper exit "
                   "code {rc}, details in the log); restart and go back to "
                   "the snapshot in the boot menu", rc=rc)
    _reinstall_own(channel)
    helper.reboot()
    say("NazoOS now runs on openSUSE Slowroll. Restart the computer to "
        "finish.")
