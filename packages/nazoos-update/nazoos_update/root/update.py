# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root action "update": zypper dup with a snapshot pair, then the extras."""

import re
import time

from nazoos_common import helper, kernel, kmp_sync, mok, proc, zypper
from nazoos_common.helper import FLATPAK, Fail, capture, run, say

from .. import status
from . import check, snapshots

# zypper: a %post script failed, the packages are installed
ZYPPER_SCRIPT_FAILED = 107
# script_failure() verdicts
OK = "ok"
KEY_MISSING = "key_missing"
FAIL = "fail"
# rpm's line for it, e.g. "warning: %post(xpadneo-ueficert-0.10.1-1.32
# .x86_64) scriptlet failed, exit status 255"
SCRIPTLET_FAILED = re.compile(r"%\w+\((\S+)-[^-]+-[^-]+\) scriptlet failed")


def nazoos_key_missing():
    """kernel-nazoos on UEFI, its signing key neither enrolled nor waiting
    for MokManager: the kernel's cert-post script then fails on every
    kernel update ("mokutil --root-pw" cannot read the yescrypt root
    hash Calamares writes, ADR 0024)."""
    if not mok.uefi():
        return False
    cert = mok.signing_cert(kernel.KERNEL_PACKAGE)
    if cert is None:
        return False
    try:
        return mok.status(cert, strict=True) == mok.MISSING
    except (Fail, OSError):
        # A broken mokutil must not turn a failed update into "only the key"
        return False


def only_trusted_certs(failed):
    """All failed scripts were the key import of *-ueficert packages whose
    key needs no MokManager: Tumbleweed's KMP keys are signed by the
    openSUSE CA in shim, but cert-post still imports them with
    "--root-pw", which cannot read Calamares' yescrypt root hash
    (ADR 0024). Nothing is missing then."""
    if not failed or not all(n.endswith("-ueficert") for n in failed):
        return False
    certs = [f for name in failed
             for f in helper.output(["rpm", "-ql", name]).split()
             if mok.CERT_PATH.fullmatch(f)]
    return bool(certs) and all(mok.covered(c) for c in certs)


def script_failure(rc, failed):
    """How to treat zypper's exit code RC after "dup": OK, KEY_MISSING
    (installed, only the kernel key import failed) or FAIL. FAILED:
    packages whose %post script failed."""
    if rc == ZYPPER_SCRIPT_FAILED and only_trusted_certs(failed):
        say("Note: the key import of " + ", ".join(failed)
            + " failed, but the key is already trusted")
        return OK
    if rc == ZYPPER_SCRIPT_FAILED and nazoos_key_missing():
        return KEY_MISSING
    return OK if rc in zypper.OK else FAIL


# Optional argument of "update", chosen in the window
CLEAN_FLATPAKS = "clean-flatpaks"


def after_update_extras(dup_ran, clean_flatpaks=False):
    """What follows the update: kernel modules (only after a dup),
    Flatpaks (unused runtimes removed only if CLEAN_FLATPAKS), the boot
    entry."""
    # dup only updates what is installed: kernel modules for
    # kernel-nazoos that came later (acpi_call); a module missing
    # from the repo is skipped there
    if dup_ran:
        try:
            kmp_sync.sync_modules()
        except (Fail, OSError) as e:
            say(f"Note: {e}")
    if proc.has("flatpak"):
        run(FLATPAK + ["update", "--noninteractive", "-y"], check=False)
    if clean_flatpaks and proc.has("flatpak"):
        run(FLATPAK + ["uninstall", "--unused", "--noninteractive", "-y"],
            check=False)
    # NazoOS kernel opt-in: a kernel update adds a new boot entry, keep
    # the chosen kernel as default (ADR 0008)
    try:
        kernel.keep_default(helper.say)
    except (Fail, OSError) as e:
        say(f"Note: {e}")


def run_dup(cmd):
    """zypper CMD inside a snapshot pair, then labels the snapshots.
    Returns True if only the NazoOS kernel key import failed."""
    failed = []

    def watch(line):
        m = SCRIPTLET_FAILED.search(line)
        if m:
            failed.append(m.group(1))

    last = snapshots.last_snapshot()
    # snapper-zypp-plugin creates a pre/post snapshot pair around this
    rc = run(zypper.ZYPPER + cmd, check=False, on_line=watch)
    snapshots.label_snapshots(update_after=last)
    verdict = script_failure(rc, failed)
    if verdict == FAIL:
        check.check_quietly()
        raise Fail("the system update failed (zypper exit code {rc})",
                   rc=rc)
    # Installed, only the key import failed: the caller finishes the update
    # (boot entry, modules) and says what to do at the end
    return verdict == KEY_MISSING


def update(args):
    if args:
        helper.arg(args, 0, (CLEAN_FLATPAKS,))
    clean_flatpaks = bool(args)
    lines = []
    rc = run(zypper.ZYPPER + ["refresh"], check=False, on_line=lines.append)
    if rc != 0:
        skipped = check.partial_refresh(rc, "".join(lines))
        if skipped:
            raise Fail("the package source {repo} does not respond; "
                       "updates wait until it works again or it is "
                       "switched off",
                       repo=", ".join(skipped))
        raise Fail("'{cmd}' failed (exit code {rc})", cmd="zypper", rc=rc)
    pkgs, problems = check.dup_preview()
    if problems:
        # dup would only fail with exit code 4; show the conflict instead
        # Not check_quietly(): it would repeat refresh, dry-run and labels
        status.write(status.new(error=status.ERROR_CONFLICT,
                                problems=problems,
                                **check.flatpak_status()))
        raise Fail("the update needs a decision: {problem}",
                   problem=problems[0])
    behind = check.mirrors_behind(pkgs)
    cmd = ["dist-upgrade", "--auto-agree-with-licenses"]
    if behind:
        say(f"Mirrors have Tumbleweed {behind[1]}, the system has "
            f"{behind[0]}: only NazoOS packages until they catch up")
        cmd = check.own_update_cmd()
    key_missing = run_dup(cmd) if cmd else False
    after_update_extras(bool(cmd), clean_flatpaks)
    reboot = capture(["zypper", "needs-rebooting"]).returncode == zypper.NEEDS_REBOOT
    # Flatpak updates may have failed (not an update error): ask again
    # instead of reporting "up to date" until the next check
    status.write(status.new(
        behind=list(behind) if behind else None, needs_reboot=reboot,
        updated=int(time.time()), **check.flatpak_status()))
    if reboot:
        helper.reboot()
    if key_missing:
        raise Fail("the update is installed, but the NazoOS kernel key is "
                   "not enrolled: open NazoOS Welcome, page Kernel, "
                   "\"Enroll key\"")
