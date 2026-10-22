# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page (ADR 0012).

Every action finds the broken parts itself; the caller only picks the action.
"""

import os
import time
from pathlib import Path

from nazoos_common import kernel, repos
from nazoos_common.grub import grub_refresh

from .. import catalog, repair
from . import maintenance
from .base import (ZYPPER, ZYPPER_IN, Fail, enable_repo, flathub_ensure,
                   output, packman_switch, rpm_installed, run, say)


def repair_repos(_args):
    # The repos belong to zypp services (ADR 0028): restore the service,
    # refresh-services adds its removed repos again but keeps disabled ones
    # disabled, so those are switched on afterwards
    for svc in catalog.REPO_SERVICES:
        if not Path(svc["dir"], "repo", "repoindex.xml").exists():
            # Package removed or damaged; its %posttrans adds the service
            run(ZYPPER + ["--gpg-auto-import-keys", "--plus-repo",
                          svc["seed"], "install", "--force",
                          "--auto-agree-with-licenses", svc["package"]])
        elif not Path("/etc/zypp/services.d",
                      svc["name"] + ".service").exists():
            run(ZYPPER + ["addservice", svc["dir"], svc["name"]])
        else:
            run(ZYPPER + ["modifyservice", "--enable", "--refresh",
                          svc["name"]])
    run(ZYPPER + ["refresh-services"])
    paths = [repos.url_path(r["url"]) for r in catalog.STANDARD_REPOS]
    for path in paths + catalog.NAZOOS_REPO_PATHS:
        alias = repos.with_path(path)
        if alias is not None:
            run(ZYPPER + ["modifyrepo", "--enable", "--refresh", alias])
    missing = [r["alias"] for r in catalog.STANDARD_REPOS
               if repos.with_path(repos.url_path(r["url"])) is None]
    if missing:
        raise Fail("still missing after restoring the services: {repos}",
                   repos=", ".join(missing))
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])


def repair_rpmdb(_args):
    run(["rpm", "--rebuilddb"])


def repair_deps(_args):
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    # Installs what is missing; never picks a conflict solution on its own
    run(ZYPPER + ["verify", "--no-recommends"])


def repair_packman(_args):
    alias, _enabled = enable_repo("/packman/")
    if alias is None:
        raise Fail("Packman is not set up; install the codecs first")
    packman_switch(alias)


def repair_nvidia(_args):
    release = os.uname().release
    flavor = release.rsplit("-", 1)[-1]
    # The module type that is installed for any kernel: G06 exists as open
    # (SUSE-signed) and closed build, both with nvidia-video-G06
    installed = output(["rpm", "-qa", "--qf", "%{NAME}\n"]).split()
    candidates = [b for b in kernel.KMP_BASES if b.startswith("nvidia-")]
    candidates += [p.removesuffix("-kmp-default")
                   for p in kernel.KMP_DEFAULT_ONLY]
    bases = [b for b in candidates
             if any(n.startswith(f"{b}-kmp-") for n in installed)]
    if bases:
        kmp = kernel.kmp(bases[0], flavor)
    else:
        # Driver without a module: the meta package names the module base
        for meta, video, *_rest in catalog.NVIDIA_DRIVERS.values():
            if rpm_installed(video):
                kmp = kernel.kmp(meta.removesuffix("-kmp-meta"), flavor)
                break
        else:
            raise Fail("no NVIDIA driver is installed")
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    run(ZYPPER_IN + ["--force", kmp])
    run(["dracut", "--force", "--kver", release])
    say("Restart the computer to load the NVIDIA driver.")


def repair_units(_args):
    units = repair.failed_units()
    for unit in units:
        if unit.endswith((".service", ".mount", ".socket")):
            run(["systemctl", "restart", unit], check=False)
    if not units:
        return
    # Check only after a moment, and never reset-failed before: that
    # hid units that fail again right after the restart
    time.sleep(repair.UNIT_SETTLE_SECONDS)
    still = repair.failed_units()
    fixed = [u for u in units if u not in still]
    if fixed:
        run(["systemctl", "reset-failed"] + fixed)
    if still:
        raise Fail("still failing: {units}", units=", ".join(still))


def repair_space(_args):
    run(["snapper", "-c", "root", "cleanup", "number"], check=False)
    run(["snapper", "-c", "root", "cleanup", "empty-pre-post"], check=False)
    maintenance.cache_clean([])
    if Path("/usr/bin/flatpak").exists():
        maintenance.flatpak_unused([])


def repair_flathub(_args):
    flathub_ensure()


def repair_boot(_args):
    run(["dracut", "--force", "--regenerate-all"])
    grub_refresh()
    say("The change takes effect after a restart.")
