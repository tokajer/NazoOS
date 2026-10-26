# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""System summary and bug report (no Qt here)."""

import os
import platform
import re
import time
from pathlib import Path

from nazoos_common import mok, proc, zypper

from . import query, units

JOURNAL_LINES = 300
RECENT_PACKAGES = 60
# Characters of the welcome log in the report
LOG_TAIL = 20000


def sysinfo(state=None):
    """Plain text summary for bug reports."""
    state = state or {}
    osr = {}
    for line in proc.read("/etc/os-release").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            osr[k] = v.strip('"')
    cpu = re.search(r"^model name\s*:\s*(.+)$", proc.read("/proc/cpuinfo"), re.M)
    mem = re.search(r"^MemTotal:\s*(\d+)", proc.read("/proc/meminfo"), re.M)
    k = state.get("kernel", {})
    sb = k["sbState"] if "sbState" in k else mok.sb_state()[2]
    if not sb:
        # mokutil explains on stderr only: firmware without Secure Boot
        # (some VMs) or legacy BIOS
        sb = ("not supported" if proc.has("mokutil")
              else "unknown (mokutil missing)")
    lines = [
        f"OS: {osr.get('PRETTY_NAME', 'unknown')} "
        f"({osr.get('VERSION_ID', '')})",
        f"Kernel: {platform.release()}",
        f"Cmdline: {proc.read('/proc/cmdline').strip()}",
        f"CPU: {cpu.group(1) if cpu else 'unknown'}",
        f"RAM: {round(int(mem.group(1)) / 1024 ** 2) if mem else '?'} GB",
        f"Session: {os.environ.get('XDG_SESSION_TYPE', '?')} / "
        f"{os.environ.get('XDG_CURRENT_DESKTOP', '?')}",
        f"Secure Boot: {sb}",
    ]
    for g in state["gpus"] if "gpus" in state else query.gpus():
        lines.append(f"GPU: {g['name']}")
    if state:
        lines.append(f"NVIDIA driver: {state.get('nvidiaDriver') or '-'}"
                     f" (loaded: {state.get('nvidiaLoaded')})")
        lines.append(f"Packman codecs: {state.get('codecs')}")
        lines.append(f"scx: {state.get('scxScheduler') or '-'}"
                     f" (active: {state.get('scxActive')})")
    return "\n".join(lines)


def report(state, findings, log):
    """Write a bug report to the home folder, return its path."""
    def section(title, text):
        return f"\n===== {title} =====\n{text.strip() or '-'}\n"

    text = "NazoOS bug report " + time.strftime("%Y-%m-%d %H:%M") + "\n"
    text += section("System", state.get("sysinfo") or sysinfo(state))
    text += section("Repair check", "\n".join(
        f"{f['id']}: {', '.join(f['items'])}" for f in findings)
        if findings is not None else "not run")
    text += section("Repositories", proc.out(
        zypper.ZYPPER + ["--no-refresh", "repos", "--uri"]))
    text += section("Failed units", "\n".join(
        units.failed_units()
        + [u + " (user)" for u in units.failed_units(user=True)]))
    text += section("Errors since boot", proc.out(
        ["journalctl", "--boot", "--priority=err", "--no-pager",
         f"--lines={JOURNAL_LINES}", "--output=short-monotonic"]))
    text += section("Recently installed packages", "\n".join(
        proc.out(["rpm", "-qa", "--last"]).splitlines()[:RECENT_PACKAGES]))
    text += section("Kernel modules (GPU)", "\n".join(
        line for line in proc.read("/proc/modules").splitlines()
        if re.match(r"(amdgpu|nvidia\w*|i915|xe|nouveau) ", line)))
    text += section("NazoOS Welcome log", log[-LOG_TAIL:])
    path = Path.home() / time.strftime("nazoos-report-%Y%m%d-%H%M%S.txt")
    path.write_text(text)
    return str(path)
