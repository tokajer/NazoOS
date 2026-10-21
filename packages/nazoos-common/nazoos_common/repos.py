# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The zypp repos and services as the files under /etc/zypp say (no Qt,
no root needed): one reader for the GUIs and the root helpers."""

import configparser
from pathlib import Path

from . import proc

REPOS_DIR = Path("/etc/zypp/repos.d")
SERVICES_DIR = Path("/etc/zypp/services.d")


def _sections(directory, pattern):
    for f in sorted(Path(directory).glob(pattern)):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read_string(proc.read(f))
        except configparser.Error:
            continue
        for alias in cp.sections():
            yield alias, cp[alias]


def _enabled(section):
    return section.get("enabled", "1").strip().lower() in (
        "1", "yes", "true", "on")


def repos():
    """(alias, first baseurl/mirrorlist URL, enabled) of every repo in
    REPOS_DIR."""
    out = []
    for alias, sec in _sections(REPOS_DIR, "*.repo"):
        # libzypp writes several baseurls as continuation lines
        urls = (sec.get("baseurl") or sec.get("mirrorlist")
                or sec.get("metalink") or "").split()
        out.append((alias, urls[0] if urls else "", _enabled(sec)))
    return out


def services():
    """{name: enabled} of the zypp services in /etc/zypp/services.d."""
    return {name: _enabled(sec)
            for name, sec in _sections(SERVICES_DIR, "*.service")}


def with_url(fragment):
    """Alias of the first repo whose baseurl contains FRAGMENT, enabled
    or not."""
    for alias, url, _on in repos():
        if fragment in url:
            return alias
    return None


def with_path(path):
    """Alias of an opensuse.org repo by URL path (any mirror host)."""
    for alias, url, _on in repos():
        if "opensuse.org" in url and url_path(url) == path:
            return alias
    return None


def url_path(url):
    """URL path without host: download. and cdn.opensuse.org match."""
    return "/" + url.split("://", 1)[-1].split("/", 1)[-1].rstrip("/") + "/"
