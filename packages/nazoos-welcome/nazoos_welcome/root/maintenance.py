# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""System page: services, updates, cleanup, snapshots, update channel."""

import os
from pathlib import Path

from nazoos_common import helper, proc, repos
from nazoos_common.helper import FLATPAK, Fail, Passthrough, arg
from nazoos_common.zypper import ZYPPER

from .. import catalog, system


def service(args):
    svc = catalog.by_id(catalog.SERVICES, arg(args, 0))
    if svc is None:
        raise Fail("unknown service")
    enable = arg(args, 1, ("on", "off")) == "on"
    if enable and not proc.rpm_installed(svc["package"]):
        helper.install([svc["package"]])
    if svc["user"]:
        return  # user units are switched by the GUI without root
    helper.run(["systemctl", "enable" if enable else "disable", "--now",
                svc["unit"]])


def system_update(_args):
    # nazoos-update knows more: no dup while the mirrors have an older
    # Tumbleweed snapshot (would only downgrade), boot menu names for the
    # snapshots, restart hint, its status file. A plain dup here
    # downgraded a fresh install (VM 2026-10-12)
    if not os.access(helper.UPDATE_HELPER, os.X_OK):
        raise Fail("nazoos-update is not installed")
    rc = helper.run([helper.UPDATE_HELPER, "update"], check=False)
    if rc:
        # Its own "@@error <reason>" line is already out: no second,
        # vaguer one on top
        raise Passthrough(rc)


def repo_refresh(_args):
    helper.run(ZYPPER + ["refresh", "--force"])


def cache_clean(_args):
    helper.run(ZYPPER + ["clean", "--all"])


def flatpak_unused(_args):
    helper.run(FLATPAK + ["uninstall", "--unused", "--noninteractive", "-y"])


def flatpak_repair(_args):
    helper.run(FLATPAK + ["repair"])


def create_snapshot(description):
    helper.run(["snapper", "-c", "root", "create", "--type", "single",
                "--cleanup-algorithm", "number", "--description", description])


def snapshot(_args):
    create_snapshot("nazoos-welcome: manual snapshot")


def _point(link, target):
    """Make the symlink LINK point to TARGET in one atomic step."""
    tmp = link.with_name(".repoindex.xml.nazoos-welcome")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    os.replace(tmp, link)


def channel(args):
    """Switch the NazoOS repo between stable (:release) and beta (:devel).

    The service swaps the repo instead of adding a second one (same
    priority would mix versions). "dup --from" then moves only our
    packages to the new channel's versions, also downwards (beta →
    stable); Tumbleweed and the kernel repo stay untouched.
    """
    target = arg(args, 0, system.CHANNEL_REPO_PATHS)
    link = Path(system.CHANNEL_LINK)
    if not link.parent.is_dir():
        raise Fail("nazoos-repos is not installed")
    # Before the link changes: the zypper snapshot alone would already
    # contain the new channel
    create_snapshot(f"nazoos-welcome: before switching to {target}")
    old = os.readlink(link) if link.is_symlink() else None
    _point(link, f"nazoos-{target}-repoindex.xml")
    try:
        helper.run(ZYPPER + ["refresh-services"])
        alias = repos.with_path(system.CHANNEL_REPO_PATHS[target])
        if alias is None:
            raise Fail("the {channel} repository did not appear after "
                       "refreshing the services", channel=target)
        helper.run(ZYPPER + ["refresh", alias])
    except Exception:
        if old:
            try:
                _point(link, old)
                helper.run(ZYPPER + ["refresh-services"], check=False)
            except OSError as e:
                helper.say(f"Note: could not restore {link}: {e}")
        raise
    # Outside the try: once dup started the packages may already be on the
    # new channel; the snapshot is the way back
    helper.run(ZYPPER + ["dist-upgrade", "--from", alias,
                         "--auto-agree-with-licenses"])
