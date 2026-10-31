# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Leave NazoOS: back to plain openSUSE Tumbleweed without reinstalling,
also when our OBS repos no longer exist (docs/leave-nazoos.md).

The transaction removes this code under the running helper: everything
used after it has to be imported here at the top, never inside a function.
"""

from pathlib import Path

from nazoos_common import grub, helper, kernel, proc, repos, shellconf
from nazoos_common.files import write_atomic
from nazoos_common.helper import Fail, say
from nazoos_common.zypper import ZYPPER, ZYPPER_IN

from .. import catalog, system
from . import apps, kernel_switch, maintenance

OWN_VENDOR = "obs://build.opensuse.org/home:Tokajer"
OWN_REPO = "home:/Tokajer"
OSS_PATH = "/tumbleweed/repo/oss/"
# zypper: installed, but an RPM script failed (man zypper, EXIT CODES). Done
# for us; not in zypper.INFO, nazoos-update reads this code differently
RPM_SCRIPT_FAILED = 107
# Installed in the transaction that removes ours, so nothing is ever
# without them
KEEP = [
    "plasma6-branding-openSUSE", "plymouth-branding-openSUSE",
    "grub2-branding-openSUSE",
    # Root is locked (ADR 0032): without this nobody can get admin rights
    "sudo-policy-wheel-auth-self",
    # ADR 0029 removed it; plain Tumbleweed has no other GUI updater once
    # nazoos-update is gone
    "discover6-backend-packagekit",
]
# All stood in nazoos-tweaks (sddm/, systemd/, modprobe.d/). There is no X
# server, the Wayland greeter dies on a VT shared with getty, and Wayland
# on NVIDIA needs modesetting: each would end in a black screen
ADMIN_FILES = {
    Path("/etc/modprobe.d/50-nvidia-wayland.conf"):
        "options nvidia_drm modeset=1 fbdev=1\n",
    Path("/etc/sddm.conf.d/10-wayland-greeter.conf"):
        "[General]\nDisplayServer=wayland\n",
    Path("/etc/systemd/system/display-manager-legacy.service.d/"
         "10-wayland-tty1.conf"):
        "[Unit]\nConflicts=getty@tty1.service\nAfter=getty@tty1.service\n",
}


def own_packages():
    """Sorted names of the installed packages we built."""
    lines = helper.output(["rpm", "-qa", "--qf", "%{NAME}\t%{VENDOR}\n"])
    return sorted({name for name, _, vendor
                   in (line.partition("\t") for line in lines.splitlines())
                   if vendor == OWN_VENDOR})


def _plan():
    """Everything up to the dry run; the system only gains a snapshot.
    Returns (alias of repo-oss, packages Tumbleweed has too, the arguments
    of the transaction)."""
    oss = repos.with_path(OSS_PATH)
    if oss is None:
        raise Fail("the openSUSE Tumbleweed repository is missing; add it "
                   "with the Repair page first")
    maintenance.create_snapshot(
        maintenance.CHANNEL_SNAPSHOT.format(target="Tumbleweed"))
    helper.run(ZYPPER + ["refresh", oss])
    names = own_packages()
    shared = [n for n in names if kernel_switch.in_repo(oss, n)]
    # No --clean-deps: it would also take what the pattern pulled in, like
    # sudo-policy-wheel-auth-self. xone-kmp-default needs xone: what
    # Tumbleweed has too stays and changes to its build afterwards
    args = KEEP + [f"-{n}" for n in names if n not in shared]
    rc = helper.run(ZYPPER_IN + ["--dry-run"] + args, check=False)
    if rc:
        raise Fail("the switch to Tumbleweed is not possible right now "
                   "(zypper exit code {rc}, details in the log); nothing "
                   "was changed", rc=rc)
    return oss, shared, args


def _set_default_zone():
    """Public, Tumbleweed's default, before the transaction: our zone file
    goes with nazoos-tweaks and firewalld does not start with a default
    zone that is gone."""
    # No --permanent: firewall-cmd refuses it next to this option, which
    # changes runtime and permanent configuration by itself
    if proc.rc(["systemctl", "is-active", "--quiet", "firewalld"]) == 0:
        helper.run(["firewall-cmd", "--set-default-zone=public"])
    elif proc.has("firewall-offline-cmd"):
        helper.run(["firewall-offline-cmd", "--set-default-zone=public"])


def _undo_settings():
    """What package removal cannot undo. Harmless on a system that stays
    NazoOS, but not taken back if the switch stops here: a gaming-mode
    boot setting then stays at desktop and the default zone at public."""
    if Path(system.SESSION_CTL).exists():
        helper.run([system.SESSION_CTL, "boot-mode", "desktop"])
    if proc.rpm_installed("waydroid"):
        apps.firewall_zone(catalog.by_id(catalog.APPS, "waydroid")["firewall"],
                           False)
    _set_default_zone()
    for path, text in ADMIN_FILES.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, text)


def _try(cmd, note):
    """The system is Tumbleweed already: a failure here is only worth a
    NOTE, the action has to end with the restart hint."""
    if helper.run(cmd, check=False):
        say(f"Note: {note}")


def _clear_top_level():
    """Back to openSUSE's boot default: only here, after the transaction,
    so stage A's pin to kernel-default survives a failed one (the next
    boot would start kernel-nazoos again). Only if it is set: the function
    always runs `grub2-set-default 0`, which would overwrite the saved
    default of a dual-boot user."""
    try:
        text = grub.GRUB_DEFAULT_FILE.read_text()
        if shellconf.get_var(text, "GRUB_TOP_LEVEL"):
            grub.clear_grub_top_level(say)
    except (Fail, OSError) as e:
        say(f"Note: the boot menu default could not be reset: {e}")


def _clean_up(oss, shared):
    if shared:
        # SHORTCUT: kernel-devel & co are multiversion, the openSUSE build
        # lands next to ours instead of replacing it. Ours stays until the
        # kernel purge takes it; revisit if that blocks a kernel update.
        _try(ZYPPER_IN + ["--oldpackage", "--force", "--from", oss] + shared,
             "some packages still are the NazoOS build: " + " ".join(shared))
    _try(ZYPPER + ["removelock", "plasma6-session-x11"],
         "the lock on plasma6-session-x11 is still there")
    _clear_top_level()
    # The menu may still name kernel-nazoos: its scripts ran next to ours
    _try(["grub2-mkconfig", "-o", str(grub.GRUB_CFG)],
         "the boot menu could not be rebuilt")
    # nazoos-repos took the service and its repos along; left are the
    # kernel repo (added by kernel-install) and what a user added
    for alias, url, _on in repos.repos():
        if OWN_REPO in url:
            _try(ZYPPER + ["removerepo", alias],
                 f"could not remove the repository {alias}")
    # By name and key id: `osc signkey --extend` changes the release part
    key = Path(kernel_switch.KERNEL_REPO_KEY).stem.rsplit("-", 1)[0]
    _try(["rpm", "-e", "--allmatches", key],
         f"could not remove the signing key {key}")


def _enable(aliases):
    for alias in aliases:
        helper.run(ZYPPER + ["modifyrepo", "--enable", alias], check=False)


def tumbleweed_switch(_args):
    """Two runs if the NazoOS kernel is in use: the first one only moves
    to the openSUSE kernel, because the running kernel must stay in place
    and a NazoOS with its repos stays usable until the second click."""
    off = []
    openSUSE_kernel = (not kernel.running_nazoos()
                       and proc.rpm_installed(kernel.KERNEL_DEFAULT))
    try:
        # A deleted OBS repo must not stop anything below. Packman stays:
        # it is the user's and has nothing to do with the end of NazoOS
        for alias, url, enabled in repos.repos():
            if enabled and OWN_REPO in url:
                helper.run(ZYPPER + ["modifyrepo", "--disable", alias])
                off.append(alias)
        if openSUSE_kernel:
            oss, shared, args = _plan()
            _undo_settings()
        else:
            kernel_switch.kernel_restore([])
    except Exception:
        _enable(off)
        raise
    if not openSUSE_kernel:
        _enable(off)
        say("Restart the computer, then click \"Switch to Tumbleweed\" "
            "again to finish.")
        helper.reboot()
        return
    with kernel_switch.efivars_read_only():
        rc = helper.run(ZYPPER_IN + args, check=False)
    if rc == RPM_SCRIPT_FAILED:
        say("Note: an RPM script failed, the packages are changed anyway")
    elif rc:
        # All still there: zypper never started (its lock, a download)
        if all(proc.rpm_installed(a[1:]) for a in args if a.startswith("-")):
            _enable(off)
            raise Fail("the switch to Tumbleweed did not start (zypper exit "
                       "code {rc}, details in the log); the NazoOS packages "
                       "were not changed, try again later", rc=rc)
        # Point of no return: the repos stay off and the snapshot is the
        # way back
        raise Fail("the switch to Tumbleweed stopped half-way (zypper exit "
                   "code {rc}, details in the log); restart and go back to "
                   "the snapshot in the boot menu", rc=rc)
    _clean_up(oss, shared)
    helper.reboot()
    say("NazoOS is removed. Restart the computer to finish.")

