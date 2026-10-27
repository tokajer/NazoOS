# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""GRUB default file, boot menu entry and kernel command line.

Root writes, the GUIs read. No Qt imports here.
"""

import re
from pathlib import Path

from . import files, helper, shellconf

GRUB_CFG = Path("/boot/grub2/grub.cfg")
GRUB_DEFAULT_FILE = Path("/etc/default/grub")
BOOT = Path("/boot")
GRUB_LOCK = Path("/run/nazoos-grub.lock")
# Matches: GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
CMDLINE_RE = re.compile(r'^GRUB_CMDLINE_LINUX_DEFAULT=(["\']?)(.*?)\1[^\S\n]*$',
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
    with files.locked(GRUB_LOCK):
        text = GRUB_DEFAULT_FILE.read_text()
        new = update(text)
        if new != text:
            files.write_atomic(GRUB_DEFAULT_FILE, new)
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
    changed = update_grub_default(lambda t: shellconf.set_var(
        shellconf.set_var(t, "GRUB_DEFAULT", "saved"), "GRUB_TOP_LEVEL", f'"{path}"'))
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
    if update_grub_default(lambda t: shellconf.set_var(t, "GRUB_TOP_LEVEL", None)):
        log("boot menu: openSUSE default order")
        helper.run(["grub2-mkconfig", "-o", str(GRUB_CFG)])
    helper.run(["grub2-set-default", "0"])


def _cmdline_match(text):
    m = CMDLINE_RE.search(text)
    if m is None:
        raise helper.Fail("GRUB_CMDLINE_LINUX_DEFAULT not found in {file}",
                          file=str(GRUB_DEFAULT_FILE))
    return m


def cmdline_options(text):
    """Options of GRUB_CMDLINE_LINUX_DEFAULT in TEXT, [] if it is missing."""
    m = CMDLINE_RE.search(text)
    return m.group(2).split() if m else []


def cmdline_set(key, option):
    """Replace the option `key` (or key=...) with `option`, None removes it.
    OPTION may be a function of the current options: it then runs under
    the GRUB lock."""
    line = ""

    def update(text):
        nonlocal line
        m = _cmdline_match(text)
        opts = [o for o in m.group(2).split() if o.split("=")[0] != key]
        new = option(m.group(2).split()) if callable(option) else option
        if new is not None:
            opts.append(new)
        line = 'GRUB_CMDLINE_LINUX_DEFAULT="' + " ".join(opts) + '"'
        return text[:m.start()] + line + text[m.end():]

    update_grub_default(update)
    helper.say(line)
    grub_refresh()
