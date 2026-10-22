# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): install, stage 2, way back, removal."""

import contextlib
import os

from nazoos_common import grub, kernel, kernelstate

from .base import (ZYPPER, ZYPPER_IN, Fail, repo_has, rpm_installed, run,
                   running_nazoos, say)
from .mok_queue import MOK_RESTART, prepare_mok

EFIVARS = "/sys/firmware/efi/efivars"


def kernel_install(_args):
    """Stage 1: kernel-nazoos next to kernel-default, default boot entry."""
    blockers = [p for p in kernel.KMP_DEFAULT_ONLY if rpm_installed(p)]
    if blockers:
        raise Fail("the closed NVIDIA driver (G06) only exists for the "
                   "openSUSE kernel; switch to the open driver first")
    alias = kernel.kernel_repo()
    if alias is None:
        alias = kernel.KERNEL_REPO_ALIAS
        run(ZYPPER + ["addrepo", "--refresh", "--priority", "90",
                      kernel.KERNEL_REPO_URL, alias])
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    # Same kernel modules as for kernel-default (NVIDIA, Xbox controllers).
    # Check first that our kernel project builds them: without its NVIDIA
    # module kernel-nazoos would start without graphics driver
    kmps = [f"{b}-kmp-nazoos" for b in kernel.KMP_BASES
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
    extra = [p for p in (f"{b}-kmp-nazoos" for b in kernel.KMP_NAZOOS_ONLY)
             if repo_has(alias, p)]
    pkgs = [kernel.KERNEL_PACKAGE] + [p for p in kmps if p not in missing] \
        + extra
    queued = prepare_mok(alias, pkgs)
    # Modules left from an earlier install stay out of "zypper in": a
    # newer build of them for the same kernel conflicts with the old one
    # and ends zypper with 4 (VM 2026-10-19); they are swapped below
    run(ZYPPER_IN + [p for p in pkgs
                     if p == kernel.KERNEL_PACKAGE or not rpm_installed(p)])
    kernel.swap_rebuilds(alias, pkgs[1:])
    kernelstate.STATE.mkdir(parents=True, exist_ok=True)
    kernelstate.PREFER.touch()
    kernelstate.write_boots({"count": 0})
    grub.ensure_grub_default(say)
    run(["systemctl", "enable", "nazoos-kernel-boot.service"])
    say(MOK_RESTART if queued
        else "Restart the computer to start the NazoOS kernel.")


def kernel_only(_args):
    """Stage 2: remove kernel-default for good (nazoos-kernel-only)."""
    if not running_nazoos():
        raise Fail("start the NazoOS kernel first")
    remove = [f"-{p}" for p in
              [kernel.KERNEL_DEFAULT, "kernel-default-base"]
              + [f"{b}-kmp-default" for b in kernel.KMP_BASES]
              if rpm_installed(p)]
    # "-name" removes in the same transaction: zypper never has to pick a
    # conflict solution on its own
    run(ZYPPER_IN + [kernel.KERNEL_ONLY_PACKAGE] + remove)


def kernel_restore(_args):
    """Way back: openSUSE kernel as default again, kernel-nazoos stays."""
    pkgs = [kernel.KERNEL_DEFAULT] + [
        f"{b}-kmp-default" for b in kernel.KMP_BASES
        if rpm_installed(f"{b}-kmp-nazoos")]
    if rpm_installed(kernel.KERNEL_ONLY_PACKAGE):
        pkgs.append(f"-{kernel.KERNEL_ONLY_PACKAGE}")
    run(ZYPPER_IN + pkgs)
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
    if not rpm_installed(kernel.KERNEL_DEFAULT):
        raise Fail("the openSUSE kernel is not installed")
    pkgs = [p for p in [kernel.KERNEL_PACKAGE, kernel.KERNEL_ONLY_PACKAGE]
            + [f"{b}-kmp-nazoos"
               for b in kernel.KMP_BASES + kernel.KMP_NAZOOS_ONLY]
            if rpm_installed(p)]
    if pkgs:
        with efivars_read_only():
            run(ZYPPER + ["remove", "--clean-deps"] + pkgs)
    kernelstate.PREFER.unlink(missing_ok=True)
    grub.clear_grub_top_level(say)
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
