# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs and handheld support."""

from nazoos_common import helper, proc

from .. import catalog
from .base import (ZYPPER, ZYPPER_IN, arg, packman_switch, repo_in_use,
                   say)


def _packman_installed():
    return "packman" in helper.output(
        ["rpm", "-qa", "--qf", "%{VENDOR}\n"]).lower()


def codecs_install(_args):
    with repo_in_use(
            "/packman/", catalog.PACKMAN_ALIAS,
            ["--refresh", "--priority", catalog.PACKMAN_PRIORITY,
             "--name", "Packman", catalog.PACKMAN_URL],
            _packman_installed) as alias:
        packman_switch(alias)
        helper.run(ZYPPER_IN + ["--from", alias] + catalog.PACKMAN_CODECS)
    helper.run(ZYPPER_IN + catalog.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, catalog.NVIDIA_DRIVERS)
    drivers = catalog.NVIDIA_DRIVERS[variant]
    with repo_in_use(
            "://download.nvidia.com/", catalog.NVIDIA_REPO_ALIAS,
            ["--refresh", "--name", "NVIDIA", catalog.NVIDIA_REPO_URL],
            lambda: any(proc.rpm_installed(p) for p in drivers)) as alias:
        helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
        helper.run(ZYPPER_IN + drivers)
    say("Restart the computer to load the NVIDIA driver.")


def rocm_install(_args):
    helper.run(ZYPPER_IN + catalog.ROCM_PACKAGES)
    say("Restart programs like Blender so they find the GPU.")


def rocm_remove(_args):
    pkgs = [p for p in catalog.ROCM_PACKAGES if proc.rpm_installed(p)]
    if pkgs:
        helper.run(ZYPPER + ["remove", "--clean-deps"] + pkgs)


def deck_install(_args):
    helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    helper.run(ZYPPER_IN + ["--type", "pattern", catalog.DECK_PATTERN])

