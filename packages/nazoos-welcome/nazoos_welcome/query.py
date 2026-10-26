# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Single system lookups without root, shared by the probes, the repair
checks and the bug report (no Qt here)."""

import re
import shlex

from nazoos_common import proc, repos

PCI_VENDORS = {"1002": "amd", "10de": "nvidia", "8086": "intel"}


def rpm_vendors(names):
    """Installed names out of `names`, with their vendor."""
    if not names:
        return {}
    found = {}
    for line in proc.out(["rpm", "-q", "--qf", "%{NAME}\t%{VENDOR}\n"]
                     + list(names)).splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            found[parts[0]] = parts[1]
    return found


def gpus():
    return parse_gpus(proc.out(["lspci", "-mm", "-nn"]))


def parse_gpus(lspci_text):
    """Display controllers out of the "lspci -mm -nn" text."""
    result = []
    for line in lspci_text.splitlines():
        try:
            f = shlex.split(line)
        except ValueError:
            continue
        if len(f) < 4 or not re.search(r"\[03(00|02|80)\]", f[1]):
            continue
        vendor_id = re.search(r"\[([0-9a-f]{4})\]$", f[2])
        vid = vendor_id.group(1) if vendor_id else ""
        vendor = PCI_VENDORS.get(vid, "other")
        name = re.sub(r"\s*\[[0-9a-f]{4}\]$", "", f[3])
        vname = re.sub(r"\s*\[[0-9a-f]{4}\]$", "", f[2])
        result.append({"vendor": vendor, "name": f"{vname} {name}"})
    return result


def flathub_configured():
    return "flathub" in proc.out(["flatpak", "remotes",
                                  "--columns=name"]).split()


def packman_repo():
    """"on" (an enabled Packman repo), "off" (only disabled ones), ""."""
    found = [on for _a, url, on in repos.repos() if "/packman/" in url]
    return "on" if any(found) else "off" if found else ""
