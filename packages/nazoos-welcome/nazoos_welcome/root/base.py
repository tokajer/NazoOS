# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Commands and lookups the root actions share."""

import os
import re
from pathlib import Path

from nazoos_common import kernel
from nazoos_common.helper import (  # noqa: F401 (used by the actions)
    FLATPAK, REPOS_DIR, ZYPPER, ZYPPER_IN, Fail, Passthrough, arg, output,
    repo_has, repo_with_url, rpm_installed, run, say)

from .. import catalog

FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
RUN_DIR = Path("/run/nazoos-welcome")


def repo_with_path(path):
    """Alias of an opensuse.org repo by URL path (any mirror host)."""
    for f in REPOS_DIR.glob("*.repo"):
        alias = None
        for line in f.read_text(errors="replace").splitlines():
            m = re.match(r"\[(.+)\]\s*$", line)
            if m:
                alias = m.group(1)
            m = re.match(r"baseurl\s*=\s*(\S+)", line)
            if (m and alias and "opensuse.org" in m.group(1)
                    and catalog.repo_path(m.group(1)) == path):
                return alias
    return None


def packman_switch(alias):
    """Switch installed multimedia packages to Packman's builds."""
    run(ZYPPER + ["--gpg-auto-import-keys", "refresh", alias])
    run(ZYPPER + ["dist-upgrade", "--auto-agree-with-licenses", "--from",
                  alias, "--allow-vendor-change", "--allow-downgrade"])


def flathub_ensure():
    run(FLATPAK + ["remote-add", "--if-not-exists", "flathub", FLATHUB_URL])


def caller():
    """(uid, name) of the user who started the helper via pkexec."""
    uid = int(os.environ.get("PKEXEC_UID", "-1"))
    name = output(["id", "-nu", str(uid)]).strip()
    if uid < 1000 or not name:
        raise Fail("unknown user")
    return uid, name


def running_nazoos():
    return os.uname().release.endswith("-nazoos")


def grub_refresh():
    if Path("/usr/sbin/update-bootloader").exists():
        run(["update-bootloader", "--refresh"])
    else:
        run(["grub2-mkconfig", "-o", str(kernel.GRUB_CFG)])


def cmdline():
    """GRUB file text, match of GRUB_CMDLINE_LINUX_DEFAULT, its options."""
    text = kernel.GRUB_DEFAULT_FILE.read_text()
    m = kernel.CMDLINE_RE.search(text)
    if m is None:
        raise Fail("GRUB_CMDLINE_LINUX_DEFAULT not found in {file}",
                   file=str(kernel.GRUB_DEFAULT_FILE))
    return text, m, m.group(2).split()


def cmdline_set(key, option):
    """Replace the option `key` (or key=...) with `option`, None removes it."""
    text, m, opts = cmdline()
    opts = [o for o in opts if o.split("=")[0] != key]
    if option is not None:
        opts.append(option)
    line = 'GRUB_CMDLINE_LINUX_DEFAULT="' + " ".join(opts) + '"'
    kernel.GRUB_DEFAULT_FILE.write_text(
        text[:m.start()] + line + text[m.end():])
    say(line)
    grub_refresh()
