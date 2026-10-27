# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs and handheld support."""

from nazoos_common import helper, proc
from nazoos_common.helper import arg, say
from nazoos_common.zypper import ZYPPER, ZYPPER_IN

from .. import system
from .base import repo_in_use
from .packman import packman_switch


def _packman_installed():
    return "packman" in helper.output(
        ["rpm", "-qa", "--qf", "%{VENDOR}\n"]).lower()


def codecs_install(_args):
    with repo_in_use(
            "/packman/", system.PACKMAN_ALIAS,
            ["--refresh", "--priority", system.PACKMAN_PRIORITY,
             "--name", "Packman", system.PACKMAN_URL],
            _packman_installed) as alias:
        packman_switch(alias)
        helper.run(ZYPPER_IN + ["--from", alias] + system.PACKMAN_CODECS)
    helper.run(ZYPPER_IN + system.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, system.NVIDIA_DRIVERS)
    drivers = system.NVIDIA_DRIVERS[variant]["packages"]
    with repo_in_use(
            "://download.nvidia.com/", system.NVIDIA_REPO_ALIAS,
            ["--refresh", "--name", "NVIDIA", system.NVIDIA_REPO_URL],
            lambda: any(proc.rpm_installed(p) for p in drivers)):
        helper.run(ZYPPER_IN + drivers)
    say("Restart the computer to load the NVIDIA driver.")


def rocm_install(_args):
    helper.run(ZYPPER_IN + system.ROCM_PACKAGES)
    say("Restart programs like Blender so they find the GPU.")


def rocm_remove(_args):
    pkgs = [p for p in system.ROCM_PACKAGES if proc.rpm_installed(p)]
    if pkgs:
        helper.run(ZYPPER + ["remove", "--clean-deps"] + pkgs)


def deck_install(_args):
    helper.run(ZYPPER + ["refresh"])
    helper.run(ZYPPER_IN + ["--type", "pattern", system.DECK_PATTERN])

