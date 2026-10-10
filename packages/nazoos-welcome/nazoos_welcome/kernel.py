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
GRUB_CFG = Path("/boot/grub2/grub.cfg")
GRUB_DEFAULT_FILE = Path("/etc/default/grub")

_SUBMENU = re.compile(r"^submenu .*\$menuentry_id_option '(gnulinux-advanced-[^']+)'")
_ENTRY = re.compile(r"^\s+menuentry .*\$menuentry_id_option "
                    r"'(gnulinux-(\S+?)-nazoos-advanced-[^']+)'")


def _version_key(version):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.-]", version)]


def nazoos_entry(cfg_text=None):
    """GRUB id "submenu>entry" of the newest kernel-nazoos, or ""."""
    if cfg_text is None:
        try:
            cfg_text = GRUB_CFG.read_text(errors="replace")
        except OSError:
            return ""
    submenu, best = "", None
    for line in cfg_text.splitlines():
        m = _SUBMENU.match(line)
        if m:
            submenu = m.group(1)
            continue
        m = _ENTRY.match(line)
        if m and submenu and "recovery" not in m.group(1):
            if best is None or _version_key(m.group(2)) > _version_key(best[1]):
                best = (m.group(1), m.group(2))
    return f"{submenu}>{best[0]}" if best else ""


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


def ensure_grub_default(log=print):
    """Root only: make the newest kernel-nazoos the default boot entry.
    GRUB_DEFAULT=saved (openSUSE default) reads the entry from grubenv."""
    entry = nazoos_entry()
    if not entry:
        log("no kernel-nazoos entry in grub.cfg")
        return False
    text = GRUB_DEFAULT_FILE.read_text()
    if not re.search(r'^GRUB_DEFAULT=["\']?saved["\']?\s*$', text, re.M):
        if re.search(r"^GRUB_DEFAULT=", text, re.M):
            text = re.sub(r"^GRUB_DEFAULT=.*$", "GRUB_DEFAULT=saved", text,
                          flags=re.M)
        else:
            text += "GRUB_DEFAULT=saved\n"
        GRUB_DEFAULT_FILE.write_text(text)
        log("GRUB_DEFAULT=saved")
    current = subprocess.run(["grub2-editenv", "list"], capture_output=True,
                             text=True).stdout
    if f"saved_entry={entry}\n" not in current + "\n":
        subprocess.run(["grub2-set-default", entry], check=True)
        log(f"default boot entry: {entry}")
    return True
