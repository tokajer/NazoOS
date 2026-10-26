# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair page (ADR 0012).

Every action finds the broken parts itself; the caller only picks the action.
"""

import http.client
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from nazoos_common import helper, kernel, proc, repos
from nazoos_common.grub import grub_refresh
from nazoos_common.helper import Fail, arg, say
from nazoos_common.zypper import ZYPPER, ZYPPER_IN, offered_keys

from .. import system, units
from . import maintenance
from .base import (enable_repo, flathub_ensure, installed_names,
                   packman_switch)


def repair_repos(_args):
    # The repos belong to zypp services (ADR 0028): restore the service,
    # refresh-services adds its removed repos again but keeps disabled ones
    # disabled, so those are switched on afterwards
    for svc in system.REPO_SERVICES:
        if not Path(svc["dir"], "repo", "repoindex.xml").exists():
            # Package removed or damaged; its %posttrans adds the service
            helper.run(ZYPPER + ["--plus-repo",
                                 svc["seed"], "install", "--force",
                                 "--auto-agree-with-licenses", svc["package"]])
        elif not Path("/etc/zypp/services.d",
                      svc["name"] + ".service").exists():
            helper.run(ZYPPER + ["addservice", svc["dir"], svc["name"]])
        else:
            helper.run(ZYPPER + ["modifyservice", "--enable", "--refresh",
                                 svc["name"]])
    helper.run(ZYPPER + ["refresh-services"])
    paths = [repos.url_path(r["url"]) for r in system.STANDARD_REPOS]
    for path in paths + system.NAZOOS_REPO_PATHS:
        alias = repos.with_path(path)
        if alias is not None:
            helper.run(ZYPPER + ["modifyrepo", "--enable", "--refresh",
                                 alias])
    missing = [r["alias"] for r in system.STANDARD_REPOS
               if repos.with_path(repos.url_path(r["url"])) is None]
    if missing:
        raise Fail("still missing after restoring the services: {repos}",
                   repos=", ".join(missing))
    helper.run(ZYPPER + ["refresh"])


# A signing key is a few KB; more is not a key
KEY_MAX_BYTES = 1 << 20


def _primary_fingerprints(colons):
    """Fingerprints of the usable primary keys in gpg --with-colons output.
    A revoked or expired primary key is logged and left out."""
    found, primary = [], False
    for line in colons.splitlines():
        fields = line.split(":")
        if fields[0] == "pub":
            primary = True
            if len(fields) > 1 and fields[1] in ("r", "e"):
                say("The key is revoked or expired.")
                primary = False
        elif fields[0] == "fpr" and primary and len(fields) > 9:
            found.append(fields[9])
            primary = False
    return found


def _import_key(url, fpr, tmp):
    """Download the key at URL; if it is exactly the key FPR, import what
    gpg verified (not the downloaded bytes) with rpm. False if the file is
    not that key or cannot be fetched."""
    keyfile = os.path.join(tmp, "key.asc")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read(KEY_MAX_BYTES)
        with open(keyfile, "wb") as f:
            f.write(data)
    except (urllib.error.URLError, http.client.HTTPException, OSError,
            ValueError) as e:
        say(f"{url}: {e}")
        return False
    # Own homedir: gpg would create /root/.gnupg otherwise
    gpg = ["gpg", "--batch", "--homedir", tmp]
    r = helper.capture(gpg + ["--show-keys", "--with-colons", keyfile])
    if _primary_fingerprints(r.stdout) != [fpr]:
        say(f"{url}: not the key {fpr}")
        return False
    helper.run(gpg + ["--import", keyfile])
    clean = os.path.join(tmp, "clean.asc")
    with open(clean, "w") as f:
        f.write(helper.capture(gpg + ["--armor", "--export", fpr]).stdout)
    helper.run(["rpm", "--import", clean])
    return True


def repair_key(args):
    """Trust the key a repo offers, after the user compared its fingerprint
    (the GUI shows the one from the refresh): zypper's own offer is read
    again and the key file must have exactly that fingerprint."""
    alias = arg(args, 0, [a for a, _url, _on in repos.repos()])
    fpr = arg(args, 1)
    if not re.fullmatch(r"[0-9A-F]{40}", fpr):
        raise Fail("invalid argument: {arg}", arg=fpr)
    r = helper.capture(ZYPPER + ["refresh", alias])
    print(r.stdout + r.stderr, end="", flush=True)
    offered = [k for k in offered_keys(r.stdout + r.stderr)
               if repos.alias_of(k["label"]) == alias]
    if not offered:
        if r.returncode != 0:
            raise Fail("the package source {repo} could not be refreshed",
                       repo=alias)
        say("The key is already trusted.")
    else:
        if offered[0]["fingerprint"] != fpr:
            raise Fail("the package source {repo} now offers a different "
                       "key ({fingerprint}); check again", repo=alias,
                       fingerprint=offered[0]["fingerprint"])
        with tempfile.TemporaryDirectory() as tmp:
            urls = [u for u in offered[0]["urls"] if u.startswith("https://")]
            if not any(_import_key(u, fpr, tmp) for u in urls):
                raise Fail("the key file of {repo} does not match the "
                           "fingerprint", repo=alias)
        helper.run(ZYPPER + ["refresh", alias])
    # Clears the finding: the status still says "key"
    if os.access(helper.UPDATE_HELPER, os.X_OK):
        helper.run([helper.UPDATE_HELPER, "check"], check=False)


def repair_rpmdb(_args):
    helper.run(["rpm", "--rebuilddb"])


def repair_deps(_args):
    helper.run(ZYPPER + ["refresh"])
    # Installs what is missing; never picks a conflict solution on its own
    helper.run(ZYPPER + ["verify", "--no-recommends"])


def repair_packman(_args):
    alias, _enabled = enable_repo("/packman/")
    if alias is None:
        raise Fail("Packman is not set up; install the codecs first")
    packman_switch(alias)


def repair_nvidia(_args):
    release = os.uname().release
    flavor = release.rsplit("-", 1)[-1]
    # The module type that is installed for any kernel: G06 exists as open
    # (SUSE-signed) and closed build, both with nvidia-video-G06
    installed = installed_names()
    candidates = [b for b in kernel.KMP_BASES if b.startswith("nvidia-")]
    candidates += [p.removesuffix("-kmp-default")
                   for p in kernel.KMP_DEFAULT_ONLY]
    bases = [b for b in candidates
             if any(n.startswith(f"{b}-kmp-") for n in installed)]
    if bases:
        kmp = kernel.kmp(bases[0], flavor)
    else:
        # Driver without a module: the meta package names the module base
        for d in system.NVIDIA_DRIVERS.values():
            if proc.rpm_installed(d["video"]):
                kmp = kernel.kmp(d["module"], flavor)
                break
        else:
            raise Fail("no NVIDIA driver is installed")
    helper.run(ZYPPER + ["refresh"])
    helper.run(ZYPPER_IN + ["--force", kmp])
    helper.run(["dracut", "--force", "--kver", release])
    say("Restart the computer to load the NVIDIA driver.")


def repair_units(_args):
    still = units.restart_failed(
        False, lambda cmd: helper.run(cmd, check=False))
    if still:
        raise Fail("still failing: {units}", units=", ".join(still))


def repair_space(_args):
    helper.run(["snapper", "-c", "root", "cleanup", "number"], check=False)
    helper.run(["snapper", "-c", "root", "cleanup", "empty-pre-post"],
               check=False)
    maintenance.cache_clean([])
    if proc.has("flatpak"):
        maintenance.flatpak_unused([])


def repair_flathub(_args):
    flathub_ensure()


def repair_boot(_args):
    helper.run(["dracut", "--force", "--regenerate-all"])
    grub_refresh()
    say("The change takes effect after a restart.")
