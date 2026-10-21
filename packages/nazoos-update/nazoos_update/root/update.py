# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root action "update": zypper dup with a snapshot pair, then the extras."""

import re
import time
from pathlib import Path

from nazoos_common import helper, kernel, mok
from nazoos_common.helper import FLATPAK, ZYPPER, Fail, capture, run

from . import check, snapshots

# zypper: a %post script failed, the packages are installed
ZYPPER_SCRIPT_FAILED = 107
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
    cert = mok.signing_cert()
    return cert is not None and mok.status(cert) == "missing"


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


def update(_args):
    key_missing = False
    failed = []

    def watch(line):
        m = SCRIPTLET_FAILED.search(line)
        if m:
            failed.append(m.group(1))

    run(ZYPPER + ["--gpg-auto-import-keys", "refresh"])
    pkgs, _problems = check.dup_preview()
    behind = check.mirrors_behind(pkgs or [])
    cmd = ["dist-upgrade", "--auto-agree-with-licenses"]
    if behind:
        print(f"Mirrors have Tumbleweed {behind[1]}, the system has "
              f"{behind[0]}: only NazoOS packages until they catch up",
              flush=True)
        cmd = check.own_update_cmd()
    if cmd:
        last = snapshots.last_snapshot()
        # snapper-zypp-plugin creates a pre/post snapshot pair around this
        rc = run(ZYPPER + cmd, check=False, on_line=watch)
        snapshots.label_snapshots(update_after=last)
        if rc == ZYPPER_SCRIPT_FAILED and only_trusted_certs(failed):
            print("Note: the key import of " + ", ".join(failed)
                  + " failed, but the key is already trusted", flush=True)
        elif rc == ZYPPER_SCRIPT_FAILED and nazoos_key_missing():
            # Installed, only the key import failed: finish the update
            # (boot entry, modules) and say what to do at the end
            key_missing = True
        elif rc not in check.ZYPPER_OK:
            check.check_quietly()
            raise Fail("the system update failed (zypper exit code {rc})",
                       rc=rc)
        # dup only updates what is installed: kernel modules for
        # kernel-nazoos that came later (acpi_call); a module missing
        # from the repo is skipped there
        try:
            kernel.sync_modules()
        except (Fail, OSError) as e:
            helper.say(f"Note: {e}")
    if Path("/usr/bin/flatpak").exists():
        run(FLATPAK + ["update", "--noninteractive", "-y"], check=False)
        run(FLATPAK + ["uninstall", "--unused", "--noninteractive", "-y"],
            check=False)
    # NazoOS kernel opt-in: a kernel update adds a new boot entry, keep
    # the chosen kernel as default (ADR 0008)
    try:
        kernel.keep_default(helper.say)
    except (Fail, OSError) as e:
        helper.say(f"Note: {e}")
    reboot = capture(["zypper", "needs-rebooting"]).returncode == 102
    check.write_status({"error": "", "problems": [], "packages": [],
                        "flatpaks": [], "reboot": False,
                        "behind": list(behind) if behind else None,
                        "needs_reboot": reboot, "updated": int(time.time())})
    if reboot:
        print("@@reboot", flush=True)
    if key_missing:
        raise Fail("the update is installed, but the NazoOS kernel key is "
                   "not enrolled: open NazoOS Welcome, page Kernel, "
                   "\"Enroll key\"")
