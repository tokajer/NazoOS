# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs, handheld support and the gaming mode."""

from pathlib import Path

from .. import catalog
from .base import (ZYPPER, ZYPPER_IN, Fail, arg, caller, output,
                   packman_switch, repo_in_use, rpm_installed, run, say)


def _packman_installed():
    return "packman" in output(
        ["rpm", "-qa", "--qf", "%{VENDOR}\n"]).lower()


def codecs_install(_args):
    with repo_in_use(
            "/packman/", catalog.PACKMAN_ALIAS,
            ["--refresh", "--priority", catalog.PACKMAN_PRIORITY,
             "--name", "Packman", catalog.PACKMAN_URL],
            _packman_installed) as alias:
        packman_switch(alias)
        run(ZYPPER_IN + ["--from", alias] + catalog.PACKMAN_CODECS)
    run(ZYPPER_IN + catalog.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, catalog.NVIDIA_DRIVERS)
    drivers = catalog.NVIDIA_DRIVERS[variant]
    with repo_in_use(
            "://download.nvidia.com/", catalog.NVIDIA_REPO_ALIAS,
            ["--refresh", "--name", "NVIDIA", catalog.NVIDIA_REPO_URL],
            lambda: any(rpm_installed(p) for p in drivers)) as alias:
        run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
        run(ZYPPER_IN + drivers)
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
