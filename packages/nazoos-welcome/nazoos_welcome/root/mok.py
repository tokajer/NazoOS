# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue the Secure Boot key of kernel-nazoos for MokManager (ADR 0024)."""

import os
import re
import subprocess
import sys
from pathlib import Path

from nazoos_common import kernelstate, mok

from .. import catalog
from .base import ZYPPER_IN, RUN_DIR, Fail, output, rpm_installed, run, say

# The GUI sends the SHA-512 crypt hash (openssl passwd -6) of the
# password the user picked for MokManager on stdin, never the password
# itself and never on the command line
MOK_HASH = re.compile(r"\$6\$[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{86}")
MOK_RESTART = ("Restart: the blue MokManager screen appears. Choose "
               "\"Enroll MOK\", \"Continue\", \"Yes\" and type the password "
               "you chose (suggested: nazoos).")


def _mark_requested():
    kernelstate.STATE.mkdir(parents=True, exist_ok=True)
    kernelstate.MOK_REQUESTED.touch()


def cert_from_download(alias):
    """Signing certificate inside the kernel package that
    "zypper install --download-only" just put into the cache."""
    cache = Path("/var/cache/zypp/packages") / alias
    rpms = sorted(cache.rglob(f"{catalog.KERNEL_PACKAGE}-[0-9]*.rpm"),
                  key=lambda f: f.stat().st_mtime)
    if not rpms:
        raise Fail("the downloaded kernel package was not found")
    files = output(["rpm", "-qlp", str(rpms[-1])]).split()
    certs = [f for f in files if mok.CERT_PATH.fullmatch(f)]
    if not certs:
        return None
    # rpm2cpio | cpio: the payload paths start with "./"
    unpack = subprocess.Popen(["rpm2cpio", str(rpms[-1])],
                              stdout=subprocess.PIPE)
    data = subprocess.run(["cpio", "--extract", "--to-stdout", "--quiet",
                           "." + certs[0]], stdin=unpack.stdout,
                          capture_output=True).stdout
    unpack.stdout.close()
    unpack.wait()
    if b"BEGIN CERTIFICATE" not in data and not data.startswith(b"\x30"):
        raise Fail("the signing certificate could not be read")
    RUN_DIR.mkdir(mode=0o700, exist_ok=True)
    # Same file name as on the installed system
    cert = RUN_DIR / Path(certs[0]).name
    cert.write_bytes(data)
    return str(cert)


def mok_queue(cert):
    """Queue CERT for MokManager with the password from the GUI.
    Returns False if nothing had to be done."""
    status = mok.status(cert)
    if status != "missing":
        if status == "pending":
            # Queued by someone else (cert-post): let the GUI show it too
            _mark_requested()
        say(f"Secure Boot key: {status}, nothing to do")
        return False
    mok_hash = sys.stdin.readline().strip()
    if not MOK_HASH.fullmatch(mok_hash):
        raise Fail("a password for the Secure Boot key is needed")
    RUN_DIR.mkdir(mode=0o700, exist_ok=True)
    hash_file = RUN_DIR / "mok.hash"
    fd = os.open(hash_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(mok_hash + "\n")
    try:
        # Same options as cert-post: --ignore-keyring, or mokutil skips a
        # key the running kernel already trusts (kernel-nazoos itself)
        rc = run(["mokutil", "--import", cert, "--hash-file", str(hash_file),
                  "--ca-check", "--ignore-keyring"], check=False)
    finally:
        hash_file.unlink(missing_ok=True)
    if rc != 0:
        raise Fail("the Secure Boot key could not be prepared (mokutil "
                   "exit code {rc})", rc=rc)
    # On a running kernel-nazoos, root's "mokutil --test-key" answers
    # "already in the built-in trusted keyring" instead of "already
    # enrolled", so an enrolled key looks missing; the import then only
    # prints "CA enrolled. Skip" with exit code 0 (VM 2026-10-19)
    if mok.status(cert) != "pending":
        say("Secure Boot key: already enrolled, nothing to do")
        return False
    _mark_requested()
    return True


def prepare_mok(alias, pkgs):
    """Queue the kernel's Secure Boot key before PKGS are installed.
    Returns True if MokManager has to run at the next boot."""
    if not mok.uefi():
        return False
    # The kernel's %post (cert-post) runs "mokutil --import --root-pw".
    # That fails on Calamares installs (yescrypt root hash, ADR 0024)
    # and zypper ends with 107. A request already waiting for
    # MokManager makes it skip, so ours goes first: download, take the
    # certificate out of the package, queue it, then install
    if rpm_installed(catalog.KERNEL_PACKAGE):
        cert = mok.signing_cert()
    else:
        run(ZYPPER_IN + ["--download-only"] + pkgs)
        cert = cert_from_download(alias)
    if cert is None:
        raise Fail("kernel-nazoos has no signing certificate")
    try:
        return mok_queue(cert)
    finally:
        if cert.startswith(str(RUN_DIR)):
            Path(cert).unlink(missing_ok=True)


def mok_import(_args):
    """Queue our signing certificate for MokManager again (button on the
    kernel page), with a password the user picks (ADR 0024)."""
    cert = mok.signing_cert()
    if cert is None:
        raise Fail("kernel-nazoos has no signing certificate")
    if mok_queue(cert):
        say(MOK_RESTART)
