# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs, handheld support and the gaming mode."""

from pathlib import Path

from .. import catalog
from .base import (ZYPPER, ZYPPER_IN, Fail, arg, caller, packman_switch,
                   repo_with_url, rpm_installed, run, say)


def codecs_install(_args):
    found = repo_with_url("/packman/")
    alias = found or catalog.PACKMAN_ALIAS
    if not found:
        run(ZYPPER + ["addrepo", "--refresh", "--priority",
                      catalog.PACKMAN_PRIORITY, "--name", "Packman",
                      catalog.PACKMAN_URL, alias])
    packman_switch(alias)
    run(ZYPPER_IN + ["--from", alias] + catalog.PACKMAN_CODECS)
    run(ZYPPER_IN + catalog.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, catalog.NVIDIA_DRIVERS)
    found = repo_with_url("download.nvidia.com")
    alias = found or catalog.NVIDIA_REPO_ALIAS
    if not found:
        run(ZYPPER + ["addrepo", "--refresh", "--name", "NVIDIA",
                      catalog.NVIDIA_REPO_URL, alias])
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    run(ZYPPER_IN + catalog.NVIDIA_DRIVERS[variant])
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
