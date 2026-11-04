# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The zypp repos and services as the files under /etc/zypp say (no Qt,
no root needed): one reader for the GUIs and the root helpers."""

import configparser
from pathlib import Path

from . import proc

REPOS_DIR = Path("/etc/zypp/repos.d")
SERVICES_DIR = Path("/etc/zypp/services.d")

# The openSUSE bases NazoOS is built for: their OBS repository name and the
# package that owns the zypp service "openSUSE" (repo-oss, non-oss, update)
OBS_REPOS = {"tumbleweed": "openSUSE_Tumbleweed",
             "slowroll": "openSUSE_Slowroll"}
BASE_PACKAGES = {"tumbleweed": "openSUSE-repos-Tumbleweed",
                 "slowroll": "openSUSE-repos-Slowroll"}
# Shipped by both builds of nazoos-repos; its URLs name the base
NAZOOS_BETA_INDEX = Path(
    "/usr/share/zypp/local/service/nazoos/repo/nazoos-beta-repoindex.xml")


def base():
    """"tumbleweed" or "slowroll". Slowroll has Tumbleweed's os-release
    (ID=opensuse-tumbleweed); the service package tells them apart."""
    for name, package in BASE_PACKAGES.items():
        if proc.rpm_installed(package):
            return name
    # Service package gone (the Repair page reinstalls it): a Tumbleweed
    # system read as Slowroll would be migrated by that repair
    if OBS_REPOS["tumbleweed"] in proc.read(NAZOOS_BETA_INDEX):
        return "tumbleweed"
    return "slowroll"


def _sections(directory, pattern):
    for f in sorted(Path(directory).glob(pattern)):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read_string(proc.read(f))
        except configparser.Error:
            continue
        for alias in cp.sections():
            yield alias, cp[alias]


def flag(section, key, default):
    """Boolean KEY of a repo or service section (zypp writes 0/1)."""
    return section.get(key, default).strip().lower() in (
        "1", "yes", "true", "on")


def _enabled(section):
    return flag(section, "enabled", "1")


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


def alias_of(label):
    """Alias of the repo whose name (alias if it has none) is LABEL, the
    way zypper prints repos in its messages; None if there is none."""
    for alias, sec in _sections(REPOS_DIR, "*.repo"):
        if sec.get("name", alias).strip() == label:
            return alias
    return None


def options(alias):
    """{key: value} of repo ALIAS as its .repo file has them, {} if there
    is none."""
    for found, sec in _sections(REPOS_DIR, "*.repo"):
        if found == alias:
            return dict(sec)
    return {}


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
