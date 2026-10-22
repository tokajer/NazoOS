# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page (ADR 0012): finds known problems without root rights.

Every finding names the helper action that fixes it. The texts shown to
the user live in RepairPage.qml, keyed by the finding id.
"""

import os
import platform
import re
import shutil
import time
from pathlib import Path

from nazoos_common import proc, repos

from . import catalog, probes

# Failed units the repair page ignores: known harmless upstream issues.
# drkonqi-coredump-pickup (drkonqi6 6.7): RuntimeMaxSec=30min, ends with
# result "timeout" after login although nothing crashed (VM 2026-10-11)
IGNORED_UNITS = {"drkonqi-coredump-pickup.service"}
# Apps started from the menu run as transient units app-<name>@<id>.service
# (or .scope). One fails when the app exits with an error, e.g. a cancelled
# password dialog of a pkexec launcher: not a system problem, and
# restarting it would start the app again.
# drkonqi-coredump-processor@ hands one crash to DrKonqi and ends with
# result "timeout" after 5 min when nobody picks it up; a crash loop left
# 26 of them (Waydroid in a VM, 2026-10-15). The crash is the problem,
# restarting the unit fixes nothing
IGNORED_UNIT_PATTERN = (r"app-.+@[0-9a-f]+\.(service|scope)"
                        r"|drkonqi-coredump-processor@.+\.service")
# Seconds to wait after restarting failed units: a Type=simple unit
# fails again only after "systemctl restart" has returned
UNIT_SETTLE_SECONDS = 3
# Free space below which the repair page warns (whichever is larger)
SPACE_MIN_GB = 5
SPACE_MIN_PERCENT = 5


def _finding(fid, items=(), fix="", user_only=False):
    return {"id": fid, "items": list(items), "fix": fix,
            "userOnly": user_only}


def repo_findings():
    """Repo services, standard Tumbleweed repos and the NazoOS repo that
    are missing or disabled."""
    found = [(url, on) for _alias, url, on in repos.repos()
             if "opensuse.org" in url]
    return repo_problems(found, repos.services())


def repo_problems(repo_list, services):
    """Names of the missing or disabled repo services, standard repos and
    the NazoOS repo. REPO_LIST: (baseurl, enabled) of the opensuse.org repos,
    SERVICES: {name: enabled}."""
    found = {}
    for url, enabled in repo_list:
        path = repos.url_path(url)
        found[path] = found.get(path, False) or enabled
    bad = [s["name"] for s in catalog.REPO_SERVICES
           if not services.get(s["name"])]
    for repo in catalog.STANDARD_REPOS:
        if found.get(repos.url_path(repo["url"])) is not True:
            bad.append(repo["alias"])
    if (not any(found.get(p) for p in catalog.NAZOOS_REPO_PATHS)
            and "nazoos" not in bad):
        bad.append("nazoos")
    return bad


def rpmdb_broken():
    return proc.rc(["rpm", "-q", "rpm"]) not in (0, 127)


def unsatisfied():
    """Packages with missing dependencies (rpm only reads, no root)."""
    text = proc.out(["rpm", "-Va", "--nofiles", "--nodigest", "--nosignature",
                 "--noscripts"], timeout=120)
    return sorted(set(re.findall(r"^Unsatisfied dependencies for (\S+):",
                                 text, re.M)))


def packman_mix():
    """openSUSE builds of packages Packman replaces, while Packman is used."""
    # A repo the user switched off on purpose is not a mix
    if probes.packman_repo() != "on":
        return []
    return mixed_packman(proc.out(["rpm", "-qa", "--qf",
                                   "%{NAME}\t%{VENDOR}\n"]))


def mixed_packman(rpm_qa_text):
    """Names of the openSUSE builds in the "NAME<tab>VENDOR" lines, if at
    least one package of the family with the same word size comes from
    Packman (packman_switch() may keep all 32-bit ones at openSUSE)."""
    family = re.compile(catalog.PACKMAN_FAMILY)
    # Per word size: names from Packman, names from openSUSE
    packman = {"64": [], "32": []}
    opensuse = {"64": [], "32": []}
    for line in rpm_qa_text.splitlines():
        name, _, vendor = line.partition("\t")
        if family.fullmatch(name):
            side = packman if "packman" in vendor.lower() else opensuse
            side["32" if name.endswith("-32bit") else "64"].append(name)
    return sorted(n for bits in packman if packman[bits]
                  for n in opensuse[bits])


def nvidia_module_missing():
    """NVIDIA driver installed, but no module for the running kernel."""
    if not probes.rpm_vendors(
            [pkgs[1] for pkgs in catalog.NVIDIA_DRIVERS.values()]):
        return False
    release = platform.release()
    moddir = Path("/usr/lib/modules", release)
    if not moddir.is_dir():
        moddir = Path("/lib/modules", release)
    return not any(moddir.rglob("nvidia.ko*"))


def failed_units(user=False):
    base = ["systemctl", "--user"] if user else ["systemctl"]
    units = [line.split()[0] for line in proc.out(
        base + ["list-units", "--failed", "--plain",
                "--no-legend"]).splitlines() if line.strip()]
    return [u for u in units if u not in IGNORED_UNITS
            and not re.fullmatch(IGNORED_UNIT_PATTERN, u)]


def low_space():
    try:
        st = os.statvfs("/")
    except OSError:
        return None
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    limit = max(SPACE_MIN_GB * 1000 ** 3,
                total * SPACE_MIN_PERCENT / 100)
    return probes.human_size(free) if free < limit else None


def flathub_missing():
    if shutil.which("flatpak") is None:
        return False
    return not probes.flathub_configured()


def check():
    """All findings, most important first. Empty list = nothing found."""
    out = []
    if rpmdb_broken():
        out.append(_finding("rpmdb", fix="repair-rpmdb"))
    bad = repo_findings()
    if bad:
        out.append(_finding("repos", bad, "repair-repos"))
    deps = unsatisfied()
    if deps:
        out.append(_finding("deps", deps, "repair-deps"))
    mix = packman_mix()
    if mix:
        out.append(_finding("packman", mix, "repair-packman"))
    if nvidia_module_missing():
        out.append(_finding("nvidia", [platform.release()], "repair-nvidia"))
    units = failed_units()
    user_units = failed_units(user=True)
    if units or user_units:
        out.append(_finding("units", units + user_units,
                            "repair-units" if units else "",
                            user_only=not units))
    space = low_space()
    if space:
        out.append(_finding("space", [space], "repair-space"))
    if flathub_missing():
        out.append(_finding("flathub", fix="repair-flathub"))
    return out


def restart_user_units():
    """Fix part without root: failed units of the user session.
    Returns the log and the units that still fail after the restart."""
    log = ""
    units = failed_units(user=True)
    for unit in units:
        log += f"$ systemctl --user restart {unit}\n"
        log += proc.out(["systemctl", "--user", "restart", unit])
    if not units:
        return log, []
    time.sleep(UNIT_SETTLE_SECONDS)
    still = failed_units(user=True)
    fixed = [u for u in units if u not in still]
    if fixed:
        proc.out(["systemctl", "--user", "reset-failed"] + fixed)
    return log, still


def report(state, findings, log):
    """Write a bug report to the home folder, return its path."""
    def section(title, text):
        return f"\n===== {title} =====\n{text.strip() or '-'}\n"

    text = "NazoOS bug report " + time.strftime("%Y-%m-%d %H:%M") + "\n"
    text += section("System", state.get("sysinfo") or probes.sysinfo(state))
    text += section("Repair check", "\n".join(
        f"{f['id']}: {', '.join(f['items'])}" for f in findings)
        if findings is not None else "not run")
    text += section("Repositories", proc.out(["zypper", "--no-refresh",
                                          "repos", "--uri"]))
    text += section("Failed units", "\n".join(
        failed_units() + [u + " (user)" for u in failed_units(user=True)]))
    text += section("Errors since boot", proc.out(
        ["journalctl", "--boot", "--priority=err", "--no-pager",
         "--lines=300", "--output=short-monotonic"]))
    text += section("Recently installed packages", "\n".join(
        proc.out(["rpm", "-qa", "--last"]).splitlines()[:60]))
    text += section("Kernel modules (GPU)", "\n".join(
        line for line in proc.read("/proc/modules").splitlines()
        if re.match(r"(amdgpu|nvidia\w*|i915|xe|nouveau) ", line)))
    text += section("NazoOS Welcome log", log[-20000:])
    path = Path.home() / time.strftime("nazoos-report-%Y%m%d-%H%M%S.txt")
    path.write_text(text)
    return str(path)
