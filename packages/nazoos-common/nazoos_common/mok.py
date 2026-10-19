# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Secure Boot key of kernel-nazoos (ADR 0024), no Qt here.

enrolled() works as a user; pending() and status() need root
(mokutil --list-new reads MokNew).
"""

import re
import subprocess

KERNEL_PACKAGE = "kernel-nazoos"
CERT_PATH = re.compile(r"/etc/uefi/certs/\w+\.crt")


def _out(cmd):
    try:
        return subprocess.run(cmd, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True,
                              timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def uefi():
    """mokutil answers = UEFI. The kernel's cert-post script then calls
    mokutil, with Secure Boot on or off."""
    try:
        return subprocess.run(["mokutil", "--sb-state"],
                              stdin=subprocess.DEVNULL,
                              capture_output=True).returncode == 0
    except OSError:
        return False


def signing_cert(package=KERNEL_PACKAGE):
    """Path of the certificate that signs PACKAGE, or None."""
    certs = [f for f in _out(["rpm", "-ql", package]).split()
             if CERT_PATH.fullmatch(f)]
    return certs[0] if certs else None


def enrolled(cert):
    """The key CERT is already enrolled. On a running kernel-nazoos
    root gets "already in the built-in trusted keyring" instead, so an
    enrolled key may look missing there (VM 2026-10-19)."""
    return "already enrolled" in _out(["mokutil", "--test-key",
                                       cert]).lower()


def fingerprint(cert):
    """SHA-1 fingerprint of CERT, lower case without colons, or ""."""
    fpr = _out(["openssl", "x509", "-in", cert, "-noout", "-fingerprint",
                "-sha1"])
    return fpr.split("=")[-1].strip().replace(":", "").lower()


def pending(cert):
    """Root only: CERT waits for MokManager at the next boot."""
    fpr = fingerprint(cert)
    queued = _out(["mokutil", "--list-new"]).lower().replace(":", "")
    return bool(fpr) and fpr in queued


def status(cert):
    """Root only: enrolled, pending (waiting for MokManager) or missing."""
    if enrolled(cert):
        return "enrolled"
    return "pending" if pending(cert) else "missing"
