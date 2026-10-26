# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""zypper command lines and exit codes shared by the GUIs' root helpers
and the kernel code (no Qt here)."""

import re

from . import proc

ZYPPER = ["zypper", "--non-interactive"]
ZYPPER_IN = ZYPPER + ["install", "--auto-agree-with-licenses"]

# zypper needs-rebooting / dup exit code: restart needed
NEEDS_REBOOT = 102
# zypper exit codes >= 100 that mean "done, but note this"
# (man zypper, EXIT CODES)
INFO = {
    NEEDS_REBOOT: "restart the computer to finish the update",
    103: "zypper updated itself; run the action again if something is missing",
    106: "some repositories could not be refreshed and were skipped",
}
# "dup --dry-run" / list-updates also end with 100 (updates) or 101 (patches)
OK = (0, 100, 101, *INFO)

# Longer than the helpers' ZYPP_LOCK_TIMEOUT (120/300 s) so a held zypp lock
# is waited for, but a hung zypper cannot block the root action forever
REPO_HAS_TIMEOUT = 360
# zypper search: no matching package
NOT_FOUND = 104


def repo_search(alias, name):
    """Exit code of searching package NAME in repo ALIAS: 0 found,
    NOT_FOUND, anything else an error (127: zypper missing, 1: hung)."""
    # --no-refresh: callers refreshed the repo right before (kernel_install
    # "refresh ALIAS", kmp_sync after the update's refresh)
    return proc.rc(ZYPPER + ["--quiet", "--no-refresh", "search",
                             "--match-exact", "--type", "package",
                             "--repo", alias, name],
                   timeout=REPO_HAS_TIMEOUT)


def repo_has(alias, name):
    """Package `name` exists in repo `alias` (zypper exit 104: not found).
    False as well if zypper is missing (proc.rc: 127) or hangs."""
    return repo_search(alias, name) == 0


def group_hex(fingerprint):
    """"4AFF5EF3C350..." -> "4AFF 5EF3 C350 ..." """
    return " ".join(fingerprint[i:i + 4]
                    for i in range(0, len(fingerprint), 4))


def offered_keys(text):
    """Signing keys a refresh was offered, from its plain text output:
    [{"label", "fingerprint" (40 hex, upper), "urls" (the gpgkey URLs
    zypper tried for that repo)}]. LABEL is the repo name zypper prints,
    not its alias (repos.alias_of)."""
    # SHORTCUT: scrapes the English refresh text (the helpers set
    # LC_ALL=C.UTF-8); if zypper rewords it no key is found and the check
    # reports a plain refresh error.
    urls, keys, key, looking = {}, [], None, None
    for line in text.splitlines():
        line = line.strip()
        m = re.fullmatch(r"Looking for gpg keys in repository (.+)\.", line)
        if m:
            looking = m.group(1)
        elif looking and line.startswith("gpgkey="):
            urls.setdefault(looking, []).append(line[len("gpgkey="):])
        elif line.startswith("New repository or package signing key"):
            key = {}
            keys.append(key)
        elif key is not None and not line:
            # The fields end at the first blank line
            key = None if key else key
        elif key is not None:
            field, _, value = line.partition(":")
            value = value.strip()
            if field == "Repository":
                key.setdefault("label", value)
            elif field == "Key Fingerprint":
                key.setdefault("fingerprint", re.sub(r"\s", "", value).upper())
    return [dict(k, urls=urls.get(k["label"], [])) for k in keys
            if "label" in k
            and re.fullmatch(r"[0-9A-F]{40}", k.get("fingerprint", ""))]
