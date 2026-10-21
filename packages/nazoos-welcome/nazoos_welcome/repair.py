# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page (ADR 0012): finds known problems without root rights.

Every finding names the helper action that fixes it. The texts shown to
the user live in RepairPage.qml, keyed by the finding id.
"""

import configparser
import os
import platform
import re
import shutil
import time
from pathlib import Path

from nazoos_common import proc

from . import catalog, system


def _finding(fid, items=(), fix="", user_only=False):
    return {"id": fid, "items": list(items), "fix": fix,
            "userOnly": user_only}


def _sections(directory, pattern):
    for f in Path(directory).glob(pattern):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read_string(proc.read(f))
        except configparser.Error:
            continue
        for alias in cp.sections():
            yield alias, cp[alias]


def _enabled(section):
    return section.get("enabled", "1").strip() == "1"


def repos():
    """Repo services, standard Tumbleweed repos and the NazoOS repo that
    are missing or disabled."""
    found = []
    for _alias, sec in _sections("/etc/zypp/repos.d", "*.repo"):
        url = sec.get("baseurl", "")
        if url and "opensuse.org" in url:
            found.append((url, _enabled(sec)))
    services = {name: _enabled(sec) for name, sec
                in _sections("/etc/zypp/services.d", "*.service")}
    return repo_problems(found, services)


def repo_problems(repos, services):
    """Names of the missing or disabled repo services, standard repos and
    the NazoOS repo. REPOS: (baseurl, enabled) of the opensuse.org repos,
    SERVICES: {name: enabled}."""
    found = {}
    for url, enabled in repos:
        path = catalog.repo_path(url)
        found[path] = found.get(path, False) or enabled
    bad = [s["name"] for s in catalog.REPO_SERVICES
           if not services.get(s["name"])]
    for repo in catalog.STANDARD_REPOS:
        if found.get(catalog.repo_path(repo["url"])) is not True:
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
    if not system.repo_present("/packman/"):
        return []
    return mixed_packman(proc.out(["rpm", "-qa", "--qf",
                                   "%{NAME}\t%{VENDOR}\n"]))


def mixed_packman(rpm_qa_text):
    """Names of the openSUSE builds in the "NAME<tab>VENDOR" lines, if at
    least one package of the family comes from Packman."""
    family = re.compile(catalog.PACKMAN_FAMILY)
    ours, theirs = [], []
    for line in rpm_qa_text.splitlines():
        name, _, vendor = line.partition("\t")
        if family.fullmatch(name):
            (ours if "packman" in vendor.lower() else theirs).append(name)
    return sorted(theirs) if ours else []


def nvidia_module_missing():
    """NVIDIA driver installed, but no module for the running kernel."""
    if not system.rpm_vendors(["nvidia-video-G07", "nvidia-video-G06"]):
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
    return [u for u in units if u not in catalog.IGNORED_UNITS
            and not re.fullmatch(catalog.IGNORED_UNIT_PATTERN, u)]


def low_space():
    try:
        st = os.statvfs("/")
    except OSError:
        return None
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    limit = max(catalog.SPACE_MIN_GB * 1000 ** 3,
                total * catalog.SPACE_MIN_PERCENT / 100)
    return system.human_size(free) if free < limit else None


def flathub_missing():
    if shutil.which("flatpak") is None:
        return False
    return "flathub" not in proc.out(["flatpak", "remotes",
                                  "--columns=name"]).split()


def check():
    """All findings, most important first. Empty list = nothing found."""
    out = []
    if rpmdb_broken():
        out.append(_finding("rpmdb", fix="repair-rpmdb"))
    bad = repos()
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
    time.sleep(catalog.UNIT_SETTLE_SECONDS)
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
    text += section("System", state.get("sysinfo") or system.sysinfo(state))
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
