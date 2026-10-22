# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Secure Boot key of kernel-nazoos (ADR 0024), no Qt here.

enrolled() works as a user; pending(), status() and covered() need root
(mokutil --list-new reads MokNew). Root actions pass strict=True.
"""

import re
import subprocess
import tempfile
from pathlib import Path

from . import helper, proc

CERT_PATH = re.compile(r"/etc/uefi/certs/\w+\.crt")
# status() answers
ENROLLED = "enrolled"
PENDING = "pending"
MISSING = "missing"


def _out(cmd, strict, expect=(), empty_ok=False):
    """Output of CMD. STRICT (root actions): no timeout, and a missing
    tool or an answer without any of the EXPECT words raises, so a
    broken mokutil never reads as "not enrolled"/"not queued".
    EMPTY_OK: no output with exit code 0 is a valid empty list."""
    if not strict:
        return proc.out(cmd)
    r = helper.capture(cmd)
    # Some answers ("MokNew is empty") may go to stderr
    text = r.stdout + r.stderr
    # mokutil 0.7.2 prints nothing for a missing MokNew (VM 2026-10-22)
    if empty_ok and r.returncode == 0 and not text.strip():
        return ""
    if not any(w in text.lower() for w in expect):
        raise helper.Fail("'{cmd}' failed (exit code {rc})",
                          cmd=" ".join(cmd[:2]), rc=r.returncode)
    return text


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


def enrolled(cert, strict=False):
    """The key CERT is already enrolled. On a running kernel-nazoos
    root's "mokutil --test-key" answers "already in the built-in trusted
    keyring" instead (VM 2026-10-19), so the fingerprint is also looked
    up in the enrolled list."""
    test = _out(["mokutil", "--test-key", cert], strict,
                ("enroll", "keyring"))
    if "already enrolled" in test.lower():
        return True
    fpr = fingerprint(cert, strict)
    listed = _out(["mokutil", "--list-enrolled"], strict,
                  ("fingerprint", "empty"), empty_ok=True).lower().replace(":", "")
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


def fingerprint(cert, strict=False):
    """SHA-1 fingerprint of CERT, lower case without colons, or ""."""
    fpr = _out(["openssl", "x509", "-in", cert, "-noout",
                "-fingerprint", "-sha1"], strict, ("fingerprint",))
    return fpr.split("=")[-1].strip().replace(":", "").lower()


def pending(cert, strict=False):
    """Root only: CERT waits for MokManager at the next boot."""
    fpr = fingerprint(cert, strict)
    queued = _out(["mokutil", "--list-new"], strict,
                  ("fingerprint", "empty"), empty_ok=True).lower().replace(":", "")
    return bool(fpr) and fpr in queued


def status(cert, strict=False):
    """Root only: ENROLLED, PENDING (waiting for MokManager) or MISSING."""
    if enrolled(cert, strict):
        return ENROLLED
    return PENDING if pending(cert, strict) else MISSING
