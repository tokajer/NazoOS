# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Secure Boot key of kernel-nazoos (ADR 0024), no Qt here.

enrolled() works as a user; pending(), status() and covered() need root
(mokutil --list-new reads MokNew).
"""

import re
import subprocess
import tempfile
from pathlib import Path

from . import proc

CERT_PATH = re.compile(r"/etc/uefi/certs/\w+\.crt")


def sb_state():
    """(uefi, secure_boot, text) from "mokutil --sb-state"; text is
    mokutil's answer ("SecureBoot enabled/disabled")."""
    try:
        r = subprocess.run(["mokutil", "--sb-state"],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False, False, ""
    text = r.stdout.strip()
    uefi = r.returncode == 0
    return uefi, uefi and "secureboot enabled" in text.lower(), text


def uefi():
    """mokutil answers = UEFI. The kernel's cert-post script then calls
    mokutil, with Secure Boot on or off."""
    return sb_state()[0]


def signing_cert(package):
    """Path of the certificate that signs PACKAGE, or None."""
    certs = [f for f in proc.out(["rpm", "-ql", package]).split()
             if CERT_PATH.fullmatch(f)]
    return certs[0] if certs else None


def password_hash(password):
    """SHA-512 crypt hash (openssl passwd -6) of PASSWORD, "" if openssl
    fails."""
    try:
        r = subprocess.run(["openssl", "passwd", "-6", "-stdin"],
                           input=password, capture_output=True, text=True,
                           timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = r.stdout.strip() if r.returncode == 0 else ""
    return out if out.startswith("$6$") else ""


def enrolled(cert):
    """The key CERT is already enrolled. On a running kernel-nazoos
    root's "mokutil --test-key" answers "already in the built-in trusted
    keyring" instead (VM 2026-10-19), so the fingerprint is also looked
    up in the enrolled list."""
    test = proc.out(["mokutil", "--test-key", cert])
    if "already enrolled" in test.lower():
        return True
    fpr = fingerprint(cert)
    listed = proc.out(["mokutil", "--list-enrolled"]).lower() \
        .replace(":", "")
    return bool(fpr) and fpr in listed


def covered(cert):
    """Root only: CERT or the CA that signed it is enrolled, so it needs
    no MokManager ("mokutil --import --ca-check" skips it). openSUSE's
    KMP keys are signed by the openSUSE CA that shim brings along."""
    if enrolled(cert):
        return True
    with tempfile.TemporaryDirectory() as d:
        try:
            subprocess.run(["mokutil", "--export"], cwd=d,
                           stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return False
        pems = "".join(proc.out(["openssl", "x509", "-inform", "DER",
                                 "-in", str(der)])
                       for der in sorted(Path(d).glob("MOK-*.der")))
        if not pems:
            return False
        bundle = Path(d, "enrolled.pem")
        bundle.write_text(pems)
        try:
            return subprocess.run(
                ["openssl", "verify", "-partial_chain", "-no_check_time",
                 "-CAfile", str(bundle), cert],
                stdin=subprocess.DEVNULL, capture_output=True,
                timeout=30).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def fingerprint(cert):
    """SHA-1 fingerprint of CERT, lower case without colons, or ""."""
    fpr = proc.out(["openssl", "x509", "-in", cert, "-noout",
                    "-fingerprint", "-sha1"])
    return fpr.split("=")[-1].strip().replace(":", "").lower()


def pending(cert):
    """Root only: CERT waits for MokManager at the next boot."""
    fpr = fingerprint(cert)
    queued = proc.out(["mokutil", "--list-new"]).lower().replace(":", "")
    return bool(fpr) and fpr in queued


def status(cert):
    """Root only: enrolled, pending (waiting for MokManager) or missing."""
    if enrolled(cert):
        return "enrolled"
    return "pending" if pending(cert) else "missing"
