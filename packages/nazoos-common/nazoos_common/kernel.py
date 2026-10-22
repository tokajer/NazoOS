# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): packages, the kernel behind the boot
entry and the kernel modules that belong to it.

The GUIs only read here; the root helpers and nazoos-kernel-boot write.
State files: kernelstate, Secure Boot key: mok. No Qt imports here.
"""

import contextlib
import fcntl
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import helper, kernelstate, repos

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

GRUB_CFG = Path("/boot/grub2/grub.cfg")
GRUB_DEFAULT_FILE = Path("/etc/default/grub")
BOOT = Path("/boot")
GRUB_LOCK = Path("/run/nazoos-grub.lock")
CMDLINE_RE = re.compile(r'^GRUB_CMDLINE_LINUX_DEFAULT=(["\']?)(.*?)\1\s*$',
                        re.M)

# Top entry "NazoOS" (id gnulinux-simple-<uuid>) and its kernel
_SIMPLE = re.compile(
    r"^menuentry .*\$menuentry_id_option '(gnulinux-simple-[^']+)'")
_LINUX = re.compile(r"^\s+linux\s+(\S+)")


def _version_key(version):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.-]", version)]


def newest_kernel(flavor, boot=BOOT):
    """Path of the newest /boot/vmlinuz-<version>-FLAVOR, or ""."""
    best = None
    for f in boot.glob(f"vmlinuz-*-{flavor}"):
        version = f.name[len("vmlinuz-"):-len(flavor) - 1]
        if best is None or _version_key(version) > _version_key(best[0]):
            best = (version, f"/boot/{f.name}")
    return best[1] if best else ""


def nazoos_entry():
    """Path of the newest kernel-nazoos, or "" if none is installed."""
    return newest_kernel("nazoos")


def top_entry(cfg_text):
    """(id, kernel path) of the top menu entry "NazoOS"."""
    entry = None
    for line in cfg_text.splitlines():
        m = _SIMPLE.match(line)
        if m:
            entry = m.group(1)
            continue
        m = _LINUX.match(line)
        if entry and m:
            return entry, m.group(1)
    return entry, ""


def update_grub_default(update):
    """Apply UPDATE (text -> text) to /etc/default/grub; True if changed."""
    # welcome, nazoos-update and the kernel file trigger may write at the
    # same time: without the lock one read-modify-write loses the other
    with contextlib.ExitStack() as stack:
        try:
            lock = stack.enter_context(open(GRUB_LOCK, "w"))
        except OSError:  # no writable /run (odd chroot): go on unlocked
            lock = None
        if lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
        text = GRUB_DEFAULT_FILE.read_text()
        new = update(text)
        if new != text:
            helper.write_atomic(GRUB_DEFAULT_FILE, new)
        return new != text


def grub_refresh():
    """Root only: rebuild the boot menu."""
    if Path("/usr/sbin/update-bootloader").exists():
        helper.run(["update-bootloader", "--refresh"])
    else:
        helper.run(["grub2-mkconfig", "-o", str(GRUB_CFG)])


def ensure_grub_default(log=print, flavor="nazoos"):
    """Root only: the top menu entry "NazoOS" boots the newest kernel of
    FLAVOR and is the default. GRUB_TOP_LEVEL (grub2 >= 2.12) picks that
    kernel; without it the top entry boots the newest kernel of any
    flavor. A default inside "Advanced options" works too, but GRUB then
    highlights "Advanced options", which looks wrong to users."""
    path = newest_kernel(flavor)
    if not path:
        log(f"no kernel-{flavor} in /boot")
        return False
    changed = update_grub_default(lambda t: helper.set_var(
        helper.set_var(t, "GRUB_DEFAULT", "saved"), "GRUB_TOP_LEVEL", f'"{path}"'))
    try:
        cfg = GRUB_CFG.read_text(errors="replace")
    except OSError:
        cfg = ""
    # endswith: grub.cfg may carry a btrfs subvolume prefix (/@/boot/...)
    if changed or not top_entry(cfg)[1].endswith(path):
        log(f"boot menu: top entry starts {path}")
        # Not update-bootloader: it does nothing when LOADER_TYPE is not grub2
        helper.run(["grub2-mkconfig", "-o", str(GRUB_CFG)])
        cfg = GRUB_CFG.read_text(errors="replace")
    entry = top_entry(cfg)[0] or "0"
    current = helper.output(["grub2-editenv", "list"])
    if f"saved_entry={entry}\n" not in current + "\n":
        helper.run(["grub2-set-default", entry])
        log(f"default boot entry: {entry}")
    return True


def clear_grub_top_level(log=print):
    """Root only: back to the openSUSE behaviour (kernel-nazoos removed)."""
    if update_grub_default(lambda t: helper.set_var(t, "GRUB_TOP_LEVEL", None)):
        log("boot menu: openSUSE default order")
        helper.run(["grub2-mkconfig", "-o", str(GRUB_CFG)])
    helper.run(["grub2-set-default", "0"])


def keep_default(log=print):
    """Root only: the chosen kernel stays the default boot entry after a
    kernel update. Returns the flavor that is kept ("nazoos"/"default"),
    None if kernel-nazoos is not involved."""
    # kernel-nazoos while the user prefers it, else kernel-default as long
    # as kernel-nazoos is still installed (the first menu entry would boot
    # the newest of both)
    if kernelstate.PREFER.exists():
        flavor = "nazoos"
    elif nazoos_entry():
        flavor = "default"
    else:
        return None
    ensure_grub_default(log, flavor=flavor)
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
