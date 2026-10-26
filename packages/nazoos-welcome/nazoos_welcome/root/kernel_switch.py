# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): install, stage 2, way back, removal."""

import contextlib
import os

from nazoos_common import grub, helper, kernel, kernelstate, kmp_sync, proc, zypper
from nazoos_common.helper import Fail, say
from nazoos_common.kernel import running_nazoos
from nazoos_common.zypper import ZYPPER, ZYPPER_IN

from .base import repo_in_use
from .mok_queue import MOK_RESTART, prepare_mok

# zypper: a lower number wins, the default is 99; 90 beats the default repos
KERNEL_REPO_PRIORITY = "90"
EFIVARS = "/sys/firmware/efi/efivars"


def in_repo(alias, name):
    """Package NAME is in repo ALIAS; a failed search raises instead of
    reading as "no build" (the NVIDIA check would blame the kernel)."""
    rc = zypper.repo_search(alias, name)
    if rc not in (0, zypper.NOT_FOUND):
        raise Fail("'{cmd}' failed (exit code {rc})", cmd="zypper search",
                   rc=rc)
    return rc == 0


def nazoos_kmps(alias):
    """Module packages to install with kernel-nazoos from repo ALIAS: the
    same as for kernel-default (NVIDIA, Xbox controllers) and those only
    kernel-nazoos has."""
    # Check first that our kernel project builds them: without its NVIDIA
    # module kernel-nazoos would start without graphics driver
    kmps = kernel.wanted_kmps()
    missing = [p for p in kmps if not in_repo(alias, p)]
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
    extra = [p for p in (kernel.kmp(b, "nazoos")
                         for b in kernel.KMP_NAZOOS_ONLY)
             if in_repo(alias, p)]
    return [p for p in kmps if p not in missing] + extra


def kernel_install(_args):
    """Stage 1: kernel-nazoos next to kernel-default, default boot entry."""
    blockers = [p for p in kernel.KMP_DEFAULT_ONLY if proc.rpm_installed(p)]
    if blockers:
        raise Fail("the closed NVIDIA driver (G06) only exists for the "
                   "openSUSE kernel; switch to the open driver first")
    with repo_in_use(kernel.KERNEL_REPO_PATH,
                     kernel.KERNEL_REPO_ALIAS,
                     ["--refresh", "--priority", KERNEL_REPO_PRIORITY,
                      kernel.KERNEL_REPO_URL],
                     lambda: proc.rpm_installed(kernel.KERNEL_PACKAGE)
                     ) as alias:
        helper.run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
        pkgs = [kernel.KERNEL_PACKAGE] + nazoos_kmps(alias)
        # If the install below fails the queued key stays (harmless:
        # MokManager enrolls it, a later install needs no key step)
        queued = prepare_mok(alias, pkgs)
        # Modules left from an earlier install stay out of "zypper in": a
        # newer build of them for the same kernel conflicts with the old
        # one and ends zypper with 4 (VM 2026-10-19); they are swapped below
        helper.run(ZYPPER_IN + [p for p in pkgs
                                if p == kernel.KERNEL_PACKAGE
                                or not proc.rpm_installed(p)])
        kmp_sync.swap_rebuilds(alias, pkgs[1:])
    kernelstate.STATE.mkdir(parents=True, exist_ok=True)
    kernelstate.PREFER.touch()
    kernelstate.write_boots({"count": 0})
    # Before the boot menu step: if that fails, the boot counter must not
    # stay off (stage 2 would never be offered)
    helper.run(["systemctl", "enable", "nazoos-kernel-boot.service"])
    grub.ensure_grub_default(say)
    say(MOK_RESTART if queued
        else "Restart the computer to start the NazoOS kernel.")


def kernel_only(_args):
    """Stage 2: remove kernel-default for good (nazoos-kernel-only)."""
    if not running_nazoos():
        raise Fail("start the NazoOS kernel first")
    stage2 = kernel.stage2_now()
    if stage2 == kernel.STAGE2_WAITING:
        raise Fail("the openSUSE kernel can be removed after {count} clean "
                   "starts of the NazoOS kernel",
                   count=kernelstate.STABLE_BOOTS)
    if stage2 != kernel.STAGE2_READY:
        raise Fail("the openSUSE kernel is already removed or was chosen "
                   "again on the Kernel page")
    remove = [f"-{p}" for p in
              [kernel.KERNEL_DEFAULT, "kernel-default-base"]
              + [kernel.kmp(b, "default") for b in kernel.KMP_BASES]
              if proc.rpm_installed(p)]
    # "-name" removes in the same transaction: zypper never has to pick a
    # conflict solution on its own
    helper.run(ZYPPER_IN + [kernel.KERNEL_ONLY_PACKAGE] + remove)


def kernel_restore(_args):
    """Way back: openSUSE kernel as default again, kernel-nazoos stays."""
    pkgs = [kernel.KERNEL_DEFAULT] + [
        kernel.kmp(b, "default") for b in kernel.KMP_BASES
        if proc.rpm_installed(kernel.kmp(b, "nazoos"))]
    if proc.rpm_installed(kernel.KERNEL_ONLY_PACKAGE):
        pkgs.append(f"-{kernel.KERNEL_ONLY_PACKAGE}")
    helper.run(ZYPPER_IN + pkgs)
    kernelstate.PREFER.unlink(missing_ok=True)
    # The top entry boots the newest kernel of any flavor, often
    # kernel-nazoos: pin it to kernel-default (nazoos-kernel-boot keeps
    # this after updates)
    if not grub.ensure_grub_default(say, flavor="default"):
        raise Fail("the openSUSE kernel is not in /boot")
    say("Restart the computer to start the openSUSE kernel.")


def kernel_remove(_args):
    """Remove kernel-nazoos completely (only from the openSUSE kernel)."""
    if running_nazoos():
        raise Fail("start the openSUSE kernel first (boot menu)")
    if not proc.rpm_installed(kernel.KERNEL_DEFAULT):
        raise Fail("the openSUSE kernel is not installed")
    pkgs = [p for p in [kernel.KERNEL_PACKAGE, kernel.KERNEL_ONLY_PACKAGE]
            + [kernel.kmp(b, "nazoos")
               for b in kernel.KMP_BASES + kernel.KMP_NAZOOS_ONLY]
            if proc.rpm_installed(p)]
    if pkgs:
        with efivars_read_only():
            helper.run(ZYPPER + ["remove", "--clean-deps"] + pkgs)
    kernelstate.PREFER.unlink(missing_ok=True)
    grub.clear_grub_top_level(say)
    helper.run(["systemctl", "disable", "nazoos-kernel-boot.service"], check=False)


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
        helper.run(["mount", "-o", "remount,ro", EFIVARS], check=False)
    try:
        yield
    finally:
        if was_rw:
            helper.run(["mount", "-o", "remount,rw", EFIVARS], check=False)
