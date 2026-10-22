# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root only: kernel module packages for kernel-nazoos that arrived later or
were rebuilt. No Qt imports here.
"""

import xml.etree.ElementTree as ET

from . import helper, kernel, proc, zypper


def sync_modules():
    """Kernel modules for kernel-nazoos that came after it was installed.

    Run by nazoos-update after "zypper dup", which only updates installed
    packages: a new KMP_NAZOOS_ONLY module (acpi_call), or a driver
    installed for kernel-default later (xone after kernel-nazoos), would
    never arrive. Only takes what the kernel repo has: a module that does
    not build right now is skipped and the update goes on (no hard
    Requires, kernel and packages stay separate).
    """
    if not proc.rpm_installed(kernel.KERNEL_PACKAGE):
        return
    alias = kernel.kernel_repo()
    if alias is None:
        helper.say("Note: the NazoOS kernel repository is missing, kernel "
                   "modules are not checked")
        return
    wanted = kernel.wanted_kmps()
    wanted += [kernel.kmp(b, "nazoos") for b in kernel.KMP_NAZOOS_ONLY]
    new = [p for p in wanted
           if not proc.rpm_installed(p) and zypper.repo_has(alias, p)]
    if new:
        helper.run(zypper.ZYPPER_IN + new)
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
        helper.run(zypper.ZYPPER_IN + ["--force-resolution"] + rebuilt)


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
            zypper.ZYPPER + ["--xmlout", "search", "--details",
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
