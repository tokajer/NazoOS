# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""System page: services, updates, cleanup, snapshots, update channel."""

import os
from pathlib import Path

from nazoos_common import helper, proc, repos

from .. import catalog
from .base import (FLATPAK, ZYPPER, ZYPPER_IN, Fail, Passthrough, arg)

# Root part of nazoos-update: one update path for both apps
UPDATE_HELPER = "/usr/libexec/nazoos-update/nazoos-update-helper"


def service(args):
    svc = catalog.by_id(catalog.SERVICES, arg(args, 0))
    if svc is None:
        raise Fail("unknown service")
    enable = arg(args, 1, ("on", "off")) == "on"
    if enable and not proc.rpm_installed(svc["package"]):
        helper.run(ZYPPER_IN + [svc["package"]])
    if svc["user"]:
        return  # user units are switched by the GUI without root
    helper.run(["systemctl", "enable" if enable else "disable", "--now",
         svc["unit"]])


def system_update(_args):
    # nazoos-update knows more: no dup while the mirrors have an older
    # Tumbleweed snapshot (would only downgrade), boot menu names for the
    # snapshots, restart hint, its status file. A plain dup here
    # downgraded a fresh install (VM 2026-10-12)
    if os.access(UPDATE_HELPER, os.X_OK):
        rc = helper.run([UPDATE_HELPER, "update"], check=False)
        if rc:
            # Its own "@@error <reason>" line is already out: no second,
            # vaguer one on top
            raise Passthrough(rc)
        return
    helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    helper.run(ZYPPER + ["dist-upgrade", "--auto-agree-with-licenses"])
    if proc.has("flatpak"):
        helper.run(FLATPAK + ["update", "--noninteractive", "-y"])


def repo_refresh(_args):
    helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh", "--force"])


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


def channel(args):
    """Switch the NazoOS repo between stable (:release) and beta (:devel).

    The service swaps the repo instead of adding a second one (same
    priority would mix versions). "dup --from" then moves only our
    packages to the new channel's versions, also downwards (beta →
    stable); Tumbleweed and the kernel repo stay untouched.
    """
    target = arg(args, 0, catalog.CHANNEL_REPO_PATHS)
    link = Path(catalog.CHANNEL_LINK)
    if not link.parent.is_dir():
        raise Fail("nazoos-repos is not installed")
    # Before the link changes: the zypper snapshot alone would already
    # contain the new channel
    create_snapshot(f"nazoos-welcome: before switching to {target}")
    tmp = link.with_name(".repoindex.xml.nazoos-welcome")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(f"nazoos-{target}-repoindex.xml")
    os.replace(tmp, link)
    helper.run(ZYPPER + ["refresh-services"])
    alias = repos.with_path(catalog.CHANNEL_REPO_PATHS[target])
    if alias is None:
        raise Fail("the {channel} repository did not appear after "
                   "refreshing the services", channel=target)
    helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    helper.run(ZYPPER + ["dist-upgrade", "--from", alias,
                  "--auto-agree-with-licenses"])
