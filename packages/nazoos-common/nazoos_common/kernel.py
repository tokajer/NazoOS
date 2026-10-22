# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): packages and the kernel modules that
belong to them.

The GUIs only read here; the root helpers and nazoos-kernel-boot write.
Boot menu and command line: grub, state files: kernelstate, Secure Boot
key: mok, module sync as root: kmp_sync. No Qt imports here.
"""

import os

from . import grub, kernelstate, proc, repos

# NazoOS kernel (ADR 0007/0008). Opt-in: the repo is added on install.
# Stage 1 installs kernel-nazoos next to kernel-default, stage 2 removes
# kernel-default with the conflict package nazoos-kernel-only.
KERNEL_REPO_ALIAS = "nazoos-kernel"
KERNEL_REPO_URL = ("https://download.opensuse.org/repositories/"
                   "home:/Tokajer:/nazoos:/kernel/openSUSE_Tumbleweed/")
KERNEL_REPO_PATH = KERNEL_REPO_URL.split("/repositories/")[1]
KERNEL_PACKAGE = "kernel-nazoos"
KERNEL_DEFAULT = "kernel-default"
KERNEL_ONLY_PACKAGE = "nazoos-kernel-only"
# Kernel module packages: <base>-kmp-default from Tumbleweed/NVIDIA,
# <base>-kmp-nazoos from our kernel project. G06 open has no nazoos build
# (ADR 0018); it stays listed so kernel_install stops with a clear error
KMP_BASES = ["nvidia-open-driver-G07-signed", "nvidia-open-driver-G06-signed",
             "xone", "xpadneo"]
# Only built for kernel-default (closed NVIDIA driver from NVIDIA's repo):
# kernel-nazoos would boot without graphics driver
KMP_DEFAULT_ONLY = ["nvidia-driver-G06-kmp-default"]
# Only built for kernel-nazoos, installed and removed with it (<base>-kmp-
# nazoos): acpi_call for handheld TDP tools (Handheld Daemon, SimpleDeckyTDP)
KMP_NAZOOS_ONLY = ["acpi_call"]


def running_nazoos():
    """The running kernel is kernel-nazoos."""
    return os.uname().release.endswith("-nazoos")


def kmp(base, flavor):
    return f"{base}-kmp-{flavor}"


def wanted_kmps():
    """<base>-kmp-nazoos for every <base>-kmp-default that is installed."""
    return [kmp(b, "nazoos") for b in KMP_BASES
            if proc.rpm_installed(kmp(b, "default"))]


def stage2_state(preferred, boots, default_installed, only):
    """Removing kernel-default (stage 2): "" (not offered: the user went
    back to the openSUSE kernel, or it is gone already), "waiting" (fewer
    than STABLE_BOOTS clean boots) or "ready"."""
    if not (preferred and default_installed and not only):
        return ""
    return "ready" if boots >= kernelstate.STABLE_BOOTS else "waiting"


def stage2_now():
    """stage2_state() of this system. rpm is only asked while the user
    prefers kernel-nazoos (the notifier calls this every hour)."""
    if not kernelstate.PREFER.exists():
        return ""
    return stage2_state(True, kernelstate.read_boots().get("count", 0),
                        proc.rpm_installed(KERNEL_DEFAULT),
                        proc.rpm_installed(KERNEL_ONLY_PACKAGE))


def stage2_due():
    """Stage 2 can be offered now (notification)."""
    return stage2_now() == "ready"


def keep_default(log=print):
    """Root only: the chosen kernel stays the default boot entry after a
    kernel update. Returns the flavor that is kept ("nazoos"/"default"),
    None if kernel-nazoos is not involved."""
    # kernel-nazoos while the user prefers it, else kernel-default as long
    # as kernel-nazoos is still installed (the first menu entry would boot
    # the newest of both)
    if kernelstate.PREFER.exists():
        flavor = "nazoos"
    elif grub.newest_kernel("nazoos"):
        flavor = "default"
    else:
        return None
    grub.ensure_grub_default(log, flavor=flavor)
    return flavor


def kernel_repo():
    """Alias of the NazoOS kernel repository, None if not configured."""
    return repos.with_url(KERNEL_REPO_PATH)
