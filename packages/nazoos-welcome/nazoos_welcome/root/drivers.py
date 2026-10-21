# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs, handheld support and the gaming mode."""

from pathlib import Path

from nazoos_common import repos

from .. import catalog
from .base import (ZYPPER, ZYPPER_IN, Fail, arg, caller, output,
                   packman_switch, rpm_installed, run, say)


def _packman_installed():
    return "packman" in output(
        ["rpm", "-qa", "--qf", "%{VENDOR}\n"]).lower()


def codecs_install(_args):
    found = repos.with_url("/packman/")
    alias = found or catalog.PACKMAN_ALIAS
    if not found:
        run(ZYPPER + ["addrepo", "--refresh", "--priority",
                      catalog.PACKMAN_PRIORITY, "--name", "Packman",
                      catalog.PACKMAN_URL, alias])
    try:
        packman_switch(alias)
        run(ZYPPER_IN + ["--from", alias] + catalog.PACKMAN_CODECS)
    except Fail:
        # No half state: a repo this run added goes again, unless
        # packages from it are already in
        if not found and not _packman_installed():
            run(ZYPPER + ["removerepo", alias], check=False)
        raise
    run(ZYPPER_IN + catalog.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, catalog.NVIDIA_DRIVERS)
    found = repos.with_url("download.nvidia.com")
    alias = found or catalog.NVIDIA_REPO_ALIAS
    if not found:
        run(ZYPPER + ["addrepo", "--refresh", "--name", "NVIDIA",
                      catalog.NVIDIA_REPO_URL, alias])
    try:
        run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
        run(ZYPPER_IN + catalog.NVIDIA_DRIVERS[variant])
    except Fail:
        if not found and not any(rpm_installed(p)
                                 for p in catalog.NVIDIA_DRIVERS[variant]):
            run(ZYPPER + ["removerepo", alias], check=False)
        raise
    say("Restart the computer to load the NVIDIA driver.")


def rocm_install(_args):
    run(ZYPPER_IN + catalog.ROCM_PACKAGES)
    say("Restart programs like Blender so they find the GPU.")


def rocm_remove(_args):
    pkgs = [p for p in catalog.ROCM_PACKAGES if rpm_installed(p)]
    if pkgs:
        run(ZYPPER + ["remove", "--clean-deps"] + pkgs)


def deck_install(_args):
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    run(ZYPPER_IN + ["--type", "pattern", catalog.DECK_PATTERN])


def session_boot_mode(args):
    """Start in Steam's gaming mode (autologin of the calling user) or
    with the normal login screen (nazoos-session-ctl)."""
    mode = arg(args, 0, ("gaming", "desktop"))
    if not Path(catalog.SESSION_CTL).exists():
        raise Fail("gaming mode is not installed (nazoos-session)")
    if mode == "gaming":
        run([catalog.SESSION_CTL, "boot-mode", "gaming", caller()[1]])
    else:
        run([catalog.SESSION_CTL, "boot-mode", "desktop"])
