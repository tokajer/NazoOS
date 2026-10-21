# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): install, stage 2, way back, removal."""

import contextlib
import os
import xml.etree.ElementTree as ET

from nazoos_common import kernelstate

from .. import catalog, kernel
from .base import (ZYPPER, ZYPPER_IN, Fail, kernel_repo, output, repo_has,
                   rpm_installed, run, running_nazoos, say)
from .mok import MOK_RESTART, prepare_mok

EFIVARS = "/sys/firmware/efi/efivars"


def kernel_install(_args):
    """Stage 1: kernel-nazoos next to kernel-default, default boot entry."""
    blockers = [p for p in catalog.KMP_DEFAULT_ONLY if rpm_installed(p)]
    if blockers:
        raise Fail("the closed NVIDIA driver (G06) only exists for the "
                   "openSUSE kernel; switch to the open driver first")
    alias = kernel_repo()
    if alias is None:
        alias = catalog.KERNEL_REPO_ALIAS
        run(ZYPPER + ["addrepo", "--refresh", "--priority", "90",
                      catalog.KERNEL_REPO_URL, alias])
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    # Same kernel modules as for kernel-default (NVIDIA, Xbox controllers).
    # Check first that our kernel project builds them: without its NVIDIA
    # module kernel-nazoos would start without graphics driver
    kmps = [f"{b}-kmp-nazoos" for b in catalog.KMP_BASES
            if rpm_installed(f"{b}-kmp-default")]
    missing = [p for p in kmps if not repo_has(alias, p)]
    gpu = [p for p in missing if p.startswith("nvidia-")]
    if gpu:
        raise Fail("the NazoOS kernel has no build of your NVIDIA driver "
                   "({packages}); switch to the open NVIDIA driver on the "
                   "Drivers page first", packages=", ".join(gpu))
    for p in missing:
        say(f"Note: {p} is not available, the device works only with "
            "the openSUSE kernel")
    # Modules only kernel-nazoos has (acpi_call): optional, skip if the
    # repo has no build yet
    extra = [p for p in (f"{b}-kmp-nazoos" for b in catalog.KMP_NAZOOS_ONLY)
             if repo_has(alias, p)]
    pkgs = [catalog.KERNEL_PACKAGE] + [p for p in kmps if p not in missing] \
        + extra
    queued = prepare_mok(alias, pkgs)
    # Modules left from an earlier install stay out of "zypper in": a
    # newer build of them for the same kernel conflicts with the old one
    # and ends zypper with 4 (VM 2026-10-19); they are swapped below
    run(ZYPPER_IN + [p for p in pkgs
                     if p == catalog.KERNEL_PACKAGE or not rpm_installed(p)])
    swap_rebuilds(alias, pkgs[1:])
    kernelstate.STATE.mkdir(parents=True, exist_ok=True)
    kernelstate.PREFER.touch()
    kernelstate.write_boots({"count": 0})
    kernel.ensure_grub_default(say)
    run(["systemctl", "enable", "nazoos-kernel-boot.service"])
    say(MOK_RESTART if queued
        else "Restart the computer to start the NazoOS kernel.")


def kernel_only(_args):
    """Stage 2: remove kernel-default for good (nazoos-kernel-only)."""
    if not running_nazoos():
        raise Fail("start the NazoOS kernel first")
    remove = [f"-{p}" for p in
              [catalog.KERNEL_DEFAULT, "kernel-default-base"]
              + [f"{b}-kmp-default" for b in catalog.KMP_BASES]
              if rpm_installed(p)]
    # "-name" removes in the same transaction: zypper never has to pick a
    # conflict solution on its own
    run(ZYPPER_IN + [catalog.KERNEL_ONLY_PACKAGE] + remove)


def kernel_restore(_args):
    """Way back: openSUSE kernel as default again, kernel-nazoos stays."""
    pkgs = [catalog.KERNEL_DEFAULT] + [
        f"{b}-kmp-default" for b in catalog.KMP_BASES
        if rpm_installed(f"{b}-kmp-nazoos")]
    if rpm_installed(catalog.KERNEL_ONLY_PACKAGE):
        pkgs.append(f"-{catalog.KERNEL_ONLY_PACKAGE}")
    run(ZYPPER_IN + pkgs)
    kernelstate.PREFER.unlink(missing_ok=True)
    # The top entry boots the newest kernel of any flavor, often
    # kernel-nazoos: pin it to kernel-default (nazoos-kernel-boot keeps
    # this after updates)
    if not kernel.ensure_grub_default(say, flavor="default"):
        raise Fail("the openSUSE kernel is not in /boot")
    say("Restart the computer to start the openSUSE kernel.")


def kernel_remove(_args):
    """Remove kernel-nazoos completely (only from the openSUSE kernel)."""
    if running_nazoos():
        raise Fail("start the openSUSE kernel first (boot menu)")
    if not rpm_installed(catalog.KERNEL_DEFAULT):
        raise Fail("the openSUSE kernel is not installed")
    pkgs = [p for p in [catalog.KERNEL_PACKAGE, catalog.KERNEL_ONLY_PACKAGE]
            + [f"{b}-kmp-nazoos"
               for b in catalog.KMP_BASES + catalog.KMP_NAZOOS_ONLY]
            if rpm_installed(p)]
    if pkgs:
        with efivars_read_only():
            run(ZYPPER + ["remove", "--clean-deps"] + pkgs)
    kernelstate.PREFER.unlink(missing_ok=True)
    kernel.clear_grub_top_level(say)
    run(["systemctl", "disable", "nazoos-kernel-boot.service"], check=False)


@contextlib.contextmanager
def efivars_read_only():
    """The kernel's cert-postun would queue our key for removal with
    "mokutil --delete --root-pw", which fails on Calamares installs
    (yescrypt, ADR 0024) and ends zypper with 107. With a read-only
    efivarfs the script skips certificate handling; the key stays
    enrolled (harmless, a later install needs no MokManager step)."""
    try:
        was_rw = not os.statvfs(EFIVARS).f_flag & os.ST_RDONLY
    except OSError:
        was_rw = False
    if was_rw:
        run(["mount", "-o", "remount,ro", EFIVARS], check=False)
    try:
        yield
    finally:
        if was_rw:
            run(["mount", "-o", "remount,rw", EFIVARS], check=False)


def kernel_sync(_args):
    """Kernel modules for kernel-nazoos that came after it was installed.

    Run by nazoos-update after "zypper dup", which only updates installed
    packages: a new KMP_NAZOOS_ONLY module (acpi_call), or a driver
    installed for kernel-default later (xone after kernel-nazoos), would
    never arrive. Only takes what the kernel repo has: a module that does
    not build right now is skipped and the update goes on (no hard
    Requires, kernel and packages stay separate).
    """
    if not rpm_installed(catalog.KERNEL_PACKAGE):
        return
    alias = kernel_repo()
    if alias is None:
        say("Note: the NazoOS kernel repository is missing, kernel "
            "modules are not checked")
        return
    wanted = [f"{b}-kmp-nazoos" for b in catalog.KMP_BASES
              if rpm_installed(f"{b}-kmp-default")]
    wanted += [f"{b}-kmp-nazoos" for b in catalog.KMP_NAZOOS_ONLY]
    new = [p for p in wanted
           if not rpm_installed(p) and repo_has(alias, p)]
    if new:
        run(ZYPPER_IN + new)
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
        run(ZYPPER_IN + ["--force-resolution"] + rebuilt)


def kmp_rebuilds(alias, names):
    """"name = edition" of repo builds of installed NAMES for a kernel
    version that is installed in another build (OBS rebuilt the module
    without a kernel update)."""
    installed = {}
    query = ["rpm", "-q", "--qf", "%{NAME} %{VERSION}-%{RELEASE}\n"]
    for line in output(query + names).splitlines():
        parts = line.split()
        if len(parts) == 2:
            installed.setdefault(parts[0], set()).add(parts[1])
    if not installed:
        return []
    try:
        root = ET.fromstring(output(
            ZYPPER + ["--xmlout", "search", "--details", "--match-exact",
                      "--type", "package", "--repo", alias]
            + sorted(installed)))
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
