# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): packages and the kernel modules that
belong to them.

The GUIs only read here; the root helpers and nazoos-kernel-boot write.
Boot menu and command line: grub, state files: kernelstate, Secure Boot
key: mok. No Qt imports here.
"""

import xml.etree.ElementTree as ET

from . import grub, helper, kernelstate, repos

# NazoOS kernel (ADR 0007/0008). Opt-in: the repo is added on install.
# Stage 1 installs kernel-nazoos next to kernel-default, stage 2 removes
# kernel-default with the conflict package nazoos-kernel-only.
KERNEL_REPO_ALIAS = "nazoos-kernel"
KERNEL_REPO_URL = ("https://download.opensuse.org/repositories/"
                   "home:/Tokajer:/nazoos:/kernel/openSUSE_Tumbleweed/")
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
    return repos.with_url(KERNEL_REPO_URL.split("/repositories/")[1])


def sync_modules():
    """Kernel modules for kernel-nazoos that came after it was installed.

    Run by nazoos-update after "zypper dup", which only updates installed
    packages: a new KMP_NAZOOS_ONLY module (acpi_call), or a driver
    installed for kernel-default later (xone after kernel-nazoos), would
    never arrive. Only takes what the kernel repo has: a module that does
    not build right now is skipped and the update goes on (no hard
    Requires, kernel and packages stay separate).
    """
    if not helper.rpm_installed(KERNEL_PACKAGE):
        return
    alias = kernel_repo()
    if alias is None:
        helper.say("Note: the NazoOS kernel repository is missing, kernel "
                   "modules are not checked")
        return
    wanted = [f"{b}-kmp-nazoos" for b in KMP_BASES
              if helper.rpm_installed(f"{b}-kmp-default")]
    wanted += [f"{b}-kmp-nazoos" for b in KMP_NAZOOS_ONLY]
    new = [p for p in wanted
           if not helper.rpm_installed(p) and helper.repo_has(alias, p)]
    if new:
        helper.run(helper.ZYPPER_IN + new)
    swap_rebuilds(alias, wanted)


def swap_rebuilds(alias, names):
    """Replace installed modules of NAMES that the repo has in a newer
    build for the same kernel version."""
    rebuilt = kmp_rebuilds(alias, names)
    if rebuilt:
        # KMPs are multiversion and conflict per kernel version: zypper
        # dup keeps the old build of a module rebuilt for the same kernel
        # forever. With the exact edition named, the only conflict to
        # resolve is the old build itself (VM 2026-10-19)
        helper.run(helper.ZYPPER_IN + ["--force-resolution"] + rebuilt)


def kmp_rebuilds(alias, names):
    """"name = edition" of repo builds of installed NAMES for a kernel
    version that is installed in another build (OBS rebuilt the module
    without a kernel update)."""
    installed = {}
    query = ["rpm", "-q", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n"]
    for line in helper.output(query + names).splitlines():
        parts = line.split()
        if len(parts) == 2:
            installed.setdefault(parts[0], set()).add(parts[1])
    if not installed:
        return []
    try:
        root = ET.fromstring(helper.output(
            helper.ZYPPER + ["--xmlout", "search", "--details",
                             "--match-exact", "--type", "package",
                             "--repo", alias] + sorted(installed)))
    except ET.ParseError:
        return []
    return rebuilds(root, installed)


def rebuilds(root, installed):
    """"name = edition" of solvables in the zypper search XML ROOT that
    are another build of an installed {name: {version-release}}."""
    result = []
    for s in root.iter("solvable"):
        name, edition = s.get("name"), s.get("edition") or ""
        # VERSION ends with the kernel version (_k7.2.11_1), RELEASE is
        # the OBS build counter
        version = edition.rsplit("-", 1)[0]
        builds = installed.get(name, set())
        if (edition not in builds
                and any(b.rsplit("-", 1)[0] == version for b in builds)):
            result.append(f"{name} = {edition}")
    return result
