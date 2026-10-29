# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root action "check": what "zypper dup" would change, written to STATUS."""

import re
import xml.etree.ElementTree as ET

from nazoos_common import proc, repos, zypper
from nazoos_common.helper import FLATPAK, Fail, capture, say

from .. import status
from . import snapshots

# Package whose version is the Tumbleweed snapshot (YYYYMMDD)
RELEASE_PKG = "openSUSE-release"
# Characters of zypper's refresh error kept in the status
DETAIL_MAX = 600
# Package names that need a restart after the update, e.g. kernel-default,
# glibc, systemd, dbus-1, nvidia-gl-G07, libQt6Core6, kwin6, sddm
REBOOT_HINT = re.compile(r"^(kernel-|glibc$|systemd$|dbus|mesa|nvidia|"
                         r"libQt6|plasma6-workspace|plasma6-desktop|kwin|sddm)")


class Recorded(Fail):
    # The check worked, its result (offline, key, conflict) is in
    # status.json; the unit lists this code in SuccessExitStatus
    rc = 3


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
    return [a for a, _url, on in repos.repos()
            if a.startswith("nazoos") and on]


def own_update_cmd():
    """While the mirrors are behind: update only packages from our repos.
    "dup --from" would also replace Tumbleweed packages our kernel repo
    rebuilds (xone, xpadneo); "update -r" keeps the vendor
    (notes/update.md)."""
    aliases = own_repos()
    if not aliases:
        return None
    cmd = ["update", "--auto-agree-with-licenses"]
    for alias in aliases:
        cmd += ["--repo", alias]
    return cmd


def skipped_repos(text):
    """Labels of the repos zypper skipped in a refresh, from its plain
    text output."""
    # SHORTCUT: scrapes the English refresh text (the helpers set
    # LC_ALL=C.UTF-8); if zypper rewords it nothing is found and the
    # check reports a plain refresh error.
    labels = re.findall(r"Skipping repository '(.+?)' because of the "
                        r"above error\.", text)
    return list(dict.fromkeys(labels))


def partial_refresh(rc, text):
    """Labels of the sources that failed to refresh while others worked
    (no key offered), else None. Only decides the message: zypper refuses
    "dup" then (orphaned packages), so the user waits or switches the
    source off."""
    if rc == 0 or zypper.offered_keys(text):
        return None
    skipped = skipped_repos(text)
    enabled = [a for a, _url, on in repos.repos() if on]
    return skipped if 0 < len(skipped) < len(enabled) else None


def dup_preview(cmd=("dist-upgrade", "--auto-agree-with-licenses")):
    """Packages a "zypper dup" (or cmd) would change, from its XML output."""
    r = capture(zypper.ZYPPER + ["--xmlout"] + list(cmd) + ["--dry-run"])
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
        return [], problems
    if r.returncode not in zypper.OK:
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
    """Pending Flatpak updates, None if Flathub could not be asked."""
    if not proc.has("flatpak"):
        return []
    r = capture(FLATPAK + ["remote-ls", "--updates",
                           "--columns=application,branch"])
    if r.returncode != 0:
        say(f"Note: Flatpak updates could not be checked: {r.stderr.strip()}")
        return None
    apps = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if parts and parts[0]:
            apps.append(parts[0] + ("//" + parts[1] if len(parts) > 1 else ""))
    return apps


def flatpak_status():
    """Status fields for status.new(): an empty list after a failed query
    must not read as "no Flatpak updates" (flatpak_failed)."""
    apps = flatpak_updates()
    return {"flatpaks": apps or [], "flatpak_failed": apps is None}


def check(_args=None):
    result = status.new()
    r = capture(zypper.ZYPPER + ["refresh"])
    say(r.stdout + r.stderr, end="")
    skipped = partial_refresh(r.returncode, r.stdout + r.stderr)
    if r.returncode != 0:
        keys = zypper.offered_keys(r.stdout + r.stderr)
        result["error"] = status.ERROR_KEY if keys else status.ERROR_REFRESH
        # zypper names the repo by its label; the Repair page needs the alias
        result["keys"] = [
            {"repo": repos.alias_of(k["label"]) or k["label"],
             "label": k["label"], "fingerprint": k["fingerprint"],
             "shown": f"{k['label']}: {zypper.group_hex(k['fingerprint'])}"}
            for k in keys]
        result["refresh_skipped"] = skipped or []
        result["detail"] = (r.stderr or r.stdout).strip()[-DETAIL_MAX:]
        status.write(result)
        if keys:
            raise Recorded("the signing key of repository {repo} is unknown "
                           "or has changed", repo=result["keys"][0]["label"])
        if skipped:
            raise Recorded("the package source {repo} does not respond; "
                           "updates wait until it works again or it is "
                           "switched off",
                           repo=", ".join(skipped))
        raise Recorded("the package sources could not be refreshed "
                       "(no internet connection?)")
    pkgs, problems = dup_preview()
    behind = mirrors_behind(pkgs)
    if problems:
        result["error"] = status.ERROR_CONFLICT
        result["problems"] = problems
    elif behind:
        # Tumbleweed waits until the mirrors have the snapshot, our own
        # packages (branding, tweaks, ...) do not depend on it
        result["behind"] = list(behind)
        cmd = own_update_cmd()
        if cmd:
            result["packages"] = dup_preview(cmd)[0]
    else:
        result["packages"] = pkgs
    result["update_needs_reboot"] = any(
        REBOOT_HINT.match(p["name"] or "") for p in result["packages"]
        if p["type"] == "package")
    result.update(flatpak_status())
    status.write(result)
    snapshots.label_snapshots()
    say(f"{len(result['packages'])} package changes, "
        f"{len(result['flatpaks'])} Flatpak updates")
    if problems:
        raise Recorded("the update needs a decision: {problem}",
                       problem=problems[0])


def check_quietly():
    try:
        check()
    except Fail:
        pass
