# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NazoOS kernel opt-in (ADR 0008): boot entry and boot counter state.

Used by the GUI (read only), the root helper and nazoos-kernel-boot.
No Qt imports here.
"""

import json
import re
import subprocess
from pathlib import Path

from . import catalog

STATE = Path(catalog.KERNEL_STATE_DIR)
# Exists while the user wants kernel-nazoos as the default boot entry
PREFER = STATE / "kernel-prefer"
# Boot counter, written by nazoos-kernel-boot.service
BOOTS = STATE / "kernel-boots.json"
# Written by the helper when it queues the Secure Boot key. MokNew is
# readable only by root, so the GUI cannot see the request itself; it
# lives until the next boot (shim runs MokManager and deletes it)
MOK_REQUESTED = STATE / "mok-requested"
GRUB_CFG = Path("/boot/grub2/grub.cfg")
GRUB_DEFAULT_FILE = Path("/etc/default/grub")
BOOT = Path("/boot")

# Top entry "NazoOS" (id gnulinux-simple-<uuid>) and its kernel
_SIMPLE = re.compile(r"^menuentry .*\$menuentry_id_option '(gnulinux-simple-[^']+)'")
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


def _set_var(text, name, value):
    """Set NAME=VALUE in /etc/default/grub text; VALUE None removes it."""
    line = f"{name}={value}" if value is not None else None
    if re.search(rf"^{name}=", text, re.M):
        return re.sub(rf"^{name}=.*\n?", line + "\n" if line else "", text,
                      flags=re.M)
    return text + (line + "\n" if line else "")


def _update_grub_default(update):
    """Apply UPDATE (text -> text) to /etc/default/grub; True if changed."""
    text = GRUB_DEFAULT_FILE.read_text()
    new = update(text)
    if new != text:
        GRUB_DEFAULT_FILE.write_text(new)
    return new != text


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
    changed = _update_grub_default(lambda t: _set_var(
        _set_var(t, "GRUB_DEFAULT", "saved"), "GRUB_TOP_LEVEL", f'"{path}"'))
    try:
        cfg = GRUB_CFG.read_text(errors="replace")
    except OSError:
        cfg = ""
    # endswith: grub.cfg may carry a btrfs subvolume prefix (/@/boot/...)
    if changed or not top_entry(cfg)[1].endswith(path):
        log(f"boot menu: top entry starts {path}")
        subprocess.run(["grub2-mkconfig", "-o", str(GRUB_CFG)], check=True,
                       stdout=subprocess.DEVNULL)
        cfg = GRUB_CFG.read_text(errors="replace")
    entry = top_entry(cfg)[0] or "0"
    current = subprocess.run(["grub2-editenv", "list"], capture_output=True,
                             text=True).stdout
    if f"saved_entry={entry}\n" not in current + "\n":
        subprocess.run(["grub2-set-default", entry], check=True)
        log(f"default boot entry: {entry}")
    return True


def clear_grub_top_level(log=print):
    """Root only: back to the openSUSE behaviour (kernel-nazoos removed)."""
    if _update_grub_default(lambda t: _set_var(t, "GRUB_TOP_LEVEL", None)):
        log("boot menu: openSUSE default order")
        subprocess.run(["grub2-mkconfig", "-o", str(GRUB_CFG)], check=True,
                       stdout=subprocess.DEVNULL)
    subprocess.run(["grub2-set-default", "0"], check=True)


def read_boots():
    try:
        return json.loads(BOOTS.read_text())
    except (OSError, ValueError):
        return {}


def write_boots(data):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = BOOTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.chmod(0o644)
    tmp.replace(BOOTS)
