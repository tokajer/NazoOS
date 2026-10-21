# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root action "check": what "zypper dup" would change, written to STATUS."""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from nazoos_common.helper import FLATPAK, ZYPPER, Fail, capture

from .. import status
from . import snapshots

# zypper exit codes that are not errors: 100-103 = informational
# (updates/reboot needed), 106 = a repository was skipped
ZYPPER_OK = (0, 100, 101, 102, 103, 106)
# Package whose version is the Tumbleweed snapshot (YYYYMMDD)
RELEASE_PKG = "openSUSE-release"
# Package names that need a restart after the update
REBOOT_HINT = re.compile(r"^(kernel-|glibc$|systemd$|dbus|mesa|nvidia|"
                         r"libQt6|plasma6-workspace|plasma6-desktop|kwin|sddm)")


def write_status(data):
    now = int(time.time())
    data["checked"] = now
    # Time of the last check that worked: the notifier only complains
    # about failing checks when they keep failing (laptop offline, ...)
    data["last_ok"] = now if not data.get("error") else \
        status.read_status().get("last_ok", 0)
    status.STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = status.STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.chmod(tmp, 0o644)
    os.replace(tmp, status.STATUS)


def zypper_messages(root):
    return [m.text or "" for m in root.iter("message")
            if m.get("type") == "error"]


def prompt_problems(root):
    """Solver problems from the prompts: zypper's XML has no <problem>
    element in dry-run mode, only the "Problem: N: ..." prompt text."""
    problems = []
    for p in root.iter("prompt"):
        text = (p.findtext("description") or "").strip()
        if not text.startswith("Problem:"):
            continue
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("Solution"):
                break
            # zypper >= 1.14.9: "Detailed information:" + "- " lines
            line = line.strip().removeprefix("- ")
            if line:
                lines.append(line)
        lines[0] = re.sub(r"^Problem:\s*(\d+:\s*)?"
                          r"(Detailed information:\s*)?", "", lines[0])
        problems.append("; ".join(line for line in lines if line))
    return problems


def own_repos():
    """Enabled NazoOS repos (nazoos-repos service aliases nazoos:nazoos-devel /
    nazoos:nazoos, plus nazoos-kernel)."""
    r = capture(["zypper", "--xmlout", "repos"])
    try:
        root = ET.fromstring(r.stdout)
    except ET.ParseError:
        return []
    return [repo.get("alias") for repo in root.iter("repo")
            if (repo.get("alias") or "").startswith("nazoos")
            and repo.get("enabled") == "1"]


def own_update_cmd():
    """While the mirrors are behind: update only packages from our repos.
    "dup --from" would also replace Tumbleweed packages our kernel repo
    rebuilds (xone, xpadneo); "update -r" keeps the vendor
    (notes/update.md)."""
    repos = own_repos()
    if not repos:
        return None
    cmd = ["update", "--auto-agree-with-licenses"]
    for alias in repos:
        cmd += ["--repo", alias]
    return cmd


def dup_preview(cmd=("dist-upgrade", "--auto-agree-with-licenses")):
    """Packages a "zypper dup" (or cmd) would change, from its XML output."""
    r = capture(ZYPPER + ["--xmlout"] + list(cmd) + ["--dry-run"])
    try:
        root = ET.fromstring(r.stdout)
    except ET.ParseError:
        raise Fail("zypper returned no readable answer") from None
    problems = [p.findtext("description") or ""
                for p in root.iter("problem")]
    # Exit code 4: the solver found a problem the user has to decide
    if r.returncode == 4 and not problems:
        problems = (prompt_problems(root) or zypper_messages(root)
                    or ["dependency problem"])
    if problems:
        return None, problems
    if r.returncode not in ZYPPER_OK:
        messages = " ".join(zypper_messages(root))
        if messages:
            raise Fail("zypper reported: {detail}", detail=messages)
        raise Fail("zypper failed (exit code {rc})", rc=r.returncode)
    pkgs = []
    summary = root.find("install-summary")
    if summary is None:
        return pkgs, []
    for group in summary:
        kind = group.tag.replace("to-", "")   # upgrade, install, remove, ...
        for s in group.iter("solvable"):
            pkgs.append({
                "name": s.get("name"),
                "kind": kind,
                "type": s.get("type"),
                "old": s.get("edition-old") or "",
                "new": s.get("edition") or "",
            })
    return pkgs, []


def mirrors_behind(pkgs):
    """The repos still have an older Tumbleweed snapshot than the installed
    system (image built before the mirrors got the new snapshot): a dup
    would only downgrade. Returns (installed, mirror) or None."""
    for p in pkgs:
        if p["name"] == RELEASE_PKG and p["type"] == "package":
            old, new = p["old"][:8], p["new"][:8]
            if new.isdigit() and old.isdigit() and new < old:
                return old, new
    return None


def flatpak_updates():
    if not Path("/usr/bin/flatpak").exists():
        return []
    r = capture(FLATPAK + ["remote-ls", "--updates",
                           "--columns=application,branch"])
    apps = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if parts and parts[0]:
            apps.append(parts[0] + ("//" + parts[1] if len(parts) > 1 else ""))
    return apps


def check(_args=None):
    result = {"error": "", "problems": [], "packages": [], "flatpaks": []}
    r = capture(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    print(r.stdout, end="", flush=True)
    if r.returncode != 0:
        result["error"] = "refresh"
        result["detail"] = (r.stderr or r.stdout).strip()[-600:]
        write_status(result)
        raise Fail("the package sources could not be refreshed "
                   "(no internet connection?)")
    pkgs, problems = dup_preview()
    behind = None if problems else mirrors_behind(pkgs)
    if problems:
        result["error"] = "conflict"
        result["problems"] = problems
    elif behind:
        # Tumbleweed waits until the mirrors have the snapshot, our own
        # packages (branding, tweaks, ...) do not depend on it
        result["behind"] = list(behind)
        cmd = own_update_cmd()
        if cmd:
            own, own_problems = dup_preview(cmd)
            result["packages"] = [] if own_problems else own
    else:
        result["packages"] = pkgs
    result["reboot"] = any(REBOOT_HINT.match(p["name"] or "")
                           for p in result["packages"]
                           if p["type"] == "package")
    result["flatpaks"] = flatpak_updates()
    write_status(result)
    snapshots.label_snapshots()
    print(f"{len(result['packages'])} package changes, "
          f"{len(result['flatpaks'])} Flatpak updates", flush=True)
    if problems:
        raise Fail("the update needs a decision: {problem}",
                   problem=problems[0])


def check_quietly():
    try:
        check()
    except Fail:
        pass
