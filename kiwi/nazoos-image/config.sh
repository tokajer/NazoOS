#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Runs by KIWI inside the image root after all packages are installed.
# Docs: https://osinside.github.io/kiwi/concept_and_workflow/shell_scripts.html
#
# Only image-only settings belong here (hostname, live user, first defaults).
# Everything installed systems must receive later goes into a package: files
# under /usr, or a %post migration. This script never runs again on
# installed systems.

set -euxo pipefail

# KIWI writes the image settings (e.g. kiwi_profiles) into /.profile.
# kiwi_profiles is a comma-separated list: "release" pulls in "live"
test -f /.profile && . /.profile
profiles=",${kiwi_profiles:-},"
has_profile() { [[ $profiles == *",$1,"* ]]; }

echo nazoos > /etc/hostname

# Services
systemctl set-default graphical.target
# No "enable sddm": Tumbleweed starts it via display-manager-legacy.service,
# sddm-qt6 registers itself through update-alternatives
systemctl enable NetworkManager.service
# wicked would fight NetworkManager over the interfaces
systemctl disable wicked.service || true
systemctl enable snapper-timeline.timer snapper-cleanup.timer
# Firewall with the NazoOS zone (nazoos-tweaks, ADR 0021). The offline
# tool works without a running firewalld, as in this chroot
systemctl enable firewalld.service
firewall-offline-cmd --set-default-zone=nazoos
# Apply the presets of our packages (90-nazoos*.preset) again: in the
# image build a service package may be installed before the preset file
# exists. Units of packages that are not in this profile are skipped
preset_units() {
  local presets=$1 units=$2 file unit
  shopt -s nullglob
  for file in "$presets"/90-nazoos*.preset; do
    while read -r _ unit _; do
      if [ -e "$units/$unit" ]; then
        echo "$unit"
      fi
    done < <(grep -E '^enable[[:space:]]+' "$file" || true)
  done
  shopt -u nullglob
}
mapfile -t system_units < <(preset_units /usr/lib/systemd/system-preset /usr/lib/systemd/system)
mapfile -t user_units < <(preset_units /usr/lib/systemd/user-preset /usr/lib/systemd/user)
if [ ${#system_units[@]} -gt 0 ]; then
  systemctl preset "${system_units[@]}"
fi
if [ ${#user_units[@]} -gt 0 ]; then
  systemctl --global preset "${user_units[@]}"
fi
# sched_ext: scx_lavd as the preselected scheduler (made for gaming
# latency; the scx package ships scx_flash). scx itself stays off until
# it is switched on in nazoos-welcome
sed -i 's/^SCX_SCHEDULER=.*/SCX_SCHEDULER=scx_lavd/' /etc/default/scx
grep -q '^SCX_SCHEDULER=scx_lavd' /etc/default/scx

if has_profile test; then
  # Test image only: ssh into the VM (test password!).
  # qemu-guest-agent needs no enable, udev starts it when the VM has the channel
  systemctl enable sshd.service
fi

if has_profile live; then
  # Autologin of the live user. openSUSE's SDDM reads the user from
  # sysconfig, and that value overrides sddm.conf. The installer resets it
  # (nazoos-postinstall)
  sed -i 's/^DISPLAYMANAGER_AUTOLOGIN=.*/DISPLAYMANAGER_AUTOLOGIN="live"/' \
    /etc/sysconfig/displaymanager
  grep -q '^DISPLAYMANAGER_AUTOLOGIN="live"' /etc/sysconfig/displaymanager
  # No screen locker in the live session: nobody knows the live password.
  # The home directory is deleted with the user by the installer
  install -d -o live -g users /home/live/.config
  printf '[Daemon]\nAutolock=false\nLockOnResume=false\n' \
    > /home/live/.config/kscreenlockerrc
  chown live:users /home/live/.config/kscreenlockerrc
  # Keyboard: the installer sets the chosen layout through
  # org.freedesktop.locale1 (Calamares keyboard module), but Plasma's KWin
  # reads it from the user's kxkbrc. With FollowLocale1 KWin follows
  # locale1 like SDDM's KWin does, so passwords and the LUKS passphrase
  # are typed with the layout the installed system gets. Live user only:
  # installed systems keep the per-user layout from System Settings
  printf '[Wayland]\nFollowLocale1=true\n' > /home/live/.config/kwinrc
  chown live:users /home/live/.config/kwinrc
fi

# Trust the signing keys of the online repos below. OBS builds from its
# own repos without signature checks, so the rpm database has no keys yet
# and zypper --non-interactive (nazoos-update, nazoos-welcome) refuses
# every repo. Key files: openSUSE-build-key and nazoos-tweaks (NazoOS)
rpm --import /usr/lib/rpm/gnupg/keys/gpg-pubkey-*.asc

# <ignore> in config.kiwi is a zypper lock that would stay in the
# installed system: keep only the X11 one. YaST may be installed later,
# if somebody wants it
zypper --non-interactive removelock yast2

# Online repos come from packages (openSUSE-repos-Tumbleweed, nazoos-repos),
# so installed systems get URL changes with updates. Test/live keep the
# default channel beta (:devel); the release ISO switches to stable (:release)
if has_profile release; then
  ln -sf nazoos-stable-repoindex.xml /usr/share/zypp/local/service/nazoos/repo/repoindex.xml
  zypper --non-interactive refresh-services
  test -f /etc/zypp/repos.d/nazoos:nazoos.repo
fi
# Fail the build if a repo service is missing: the scriptlets of the
# repo packages ignore errors
test -f /etc/zypp/services.d/openSUSE.service
test -f /etc/zypp/services.d/nazoos.service
