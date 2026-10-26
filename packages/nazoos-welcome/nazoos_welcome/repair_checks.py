# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page (ADR 0012): finds known problems without root rights
(no Qt here).

Every finding names the helper action that fixes it. The texts shown to
the user live in RepairPage.qml, keyed by the finding id.
"""

import json
import os
import platform
import re
from pathlib import Path

from nazoos_common import proc, repos, zypper

from . import hw, query, system, units

# Free space below which the repair page warns (whichever is larger)
SPACE_MIN_GB = 5
SPACE_MIN_PERCENT = 5
# Written by nazoos-update's check, world-readable; nazoos_update is a
# separate package, so it is not imported here
UPDATE_STATUS = Path("/var/lib/nazoos-update/status.json")
# status.ERROR_KEY of nazoos-update
UPDATE_ERROR_KEY = "key"


def _finding(fid, items=(), fix="", user_fix=False, args=()):
    return {"id": fid, "items": list(items), "fix": fix,
            "userFix": user_fix, "args": list(args)}


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
    bad = [s["name"] for s in system.REPO_SERVICES
           if not services.get(s["name"])]
    for repo in system.STANDARD_REPOS:
        if found.get(repos.url_path(repo["url"])) is not True:
            bad.append(repo["alias"])
    if (not any(found.get(p) for p in system.NAZOOS_REPO_PATHS)
            and "nazoos" not in bad):
        bad.append("nazoos")
    return bad


def untrusted_keys():
    """Repo keys the last update check could not trust: [{"repo" (alias),
    "label", "fingerprint"}]."""
    try:
        st = json.loads(UPDATE_STATUS.read_text())
        if st.get("error") != UPDATE_ERROR_KEY:
            return []
        return [k for k in st["keys"] if k["repo"] and k["label"]
                and re.fullmatch(r"[0-9A-F]{40}", k["fingerprint"])]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


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
    if query.packman_repo() != "on":
        return []
    return mixed_packman(proc.out(["rpm", "-qa", "--qf",
                                   "%{NAME}\t%{VENDOR}\n"]))


def mixed_packman(rpm_qa_text):
    """Names of the openSUSE builds in the "NAME<tab>VENDOR" lines, if at
    least one package of the family with the same word size comes from
    Packman (packman_switch() may keep all 32-bit ones at openSUSE)."""
    family = re.compile(system.PACKMAN_FAMILY)
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
    if not query.rpm_vendors(
            [d["video"] for d in system.NVIDIA_DRIVERS.values()]):
        return False
    release = platform.release()
    moddir = Path("/usr/lib/modules", release)
    if not moddir.is_dir():
        moddir = Path("/lib/modules", release)
    return not any(moddir.rglob("nvidia.ko*"))


def low_space():
    try:
        st = os.statvfs("/")
    except OSError:
        return None
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    limit = max(SPACE_MIN_GB * 1000 ** 3,
                total * SPACE_MIN_PERCENT / 100)
    return hw.human_size(free) if free < limit else None


def flathub_missing():
    if not proc.has("flatpak"):
        return False
    return not query.flathub_configured()


def check():
    """All findings, most important first. Empty list = nothing found."""
    out = []
    if rpmdb_broken():
        out.append(_finding("rpmdb", fix="repair-rpmdb"))
    bad = repo_findings()
    if bad:
        out.append(_finding("repos", bad, "repair-repos"))
    for key in untrusted_keys():
        shown = f"{key['label']}: {zypper.group_hex(key['fingerprint'])}"
        out.append(_finding("key", [shown], "repair-key",
                            args=[key["repo"], key["fingerprint"]]))
    deps = unsatisfied()
    if deps:
        out.append(_finding("deps", deps, "repair-deps"))
    mix = packman_mix()
    if mix:
        out.append(_finding("packman", mix, "repair-packman"))
    if nvidia_module_missing():
        out.append(_finding("nvidia", [platform.release()], "repair-nvidia"))
    failed = units.failed_units()
    user_failed = units.failed_units(user=True)
    if failed or user_failed:
        out.append(_finding("units", failed + user_failed,
                            "repair-units" if failed else "",
                            user_fix=bool(user_failed)))
    space = low_space()
    if space:
        out.append(_finding("space", [space], "repair-space"))
    if flathub_missing():
        out.append(_finding("flathub", fix="repair-flathub"))
    return out

