#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Runs by KIWI inside the image root after all packages are installed.
# Docs: https://osinside.github.io/kiwi/concept_and_workflow/shell_scripts.html

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
# Apply our presets (nazoos-tweaks) again: in the image build a service
# package may be installed before the preset file exists
systemctl preset coolercontrold.service fwupd-refresh.timer nazoos-xone-firmware.timer
# nazoos-update: system timer (repo check) and user timer (notifications)
systemctl preset nazoos-update-check.timer nazoos-update-label.path
systemctl --global preset nazoos-update-notify.timer
# nazoos-session: gaming mode at boot (system) and session start (user)
systemctl preset nazoos-session-boot.service
systemctl --global preset nazoos-session-gaming.service nazoos-session-desktop.service \
  nazoos-session-failed.service
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
  # Handheld services (nazoos-deck, live profile only): they start only on
  # matching hardware; desktop installs remove the packages
  systemctl preset jupiter-fan-control.service pipewire-sysconf.service \
    wireplumber-sysconf.service
  systemctl --global preset steamos-powerbuttond.service
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

# Online repos for the finished system; the OBS build repos are not kept
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/tumbleweed/repo/oss/ repo-oss
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/tumbleweed/repo/non-oss/ repo-non-oss
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/update/tumbleweed/ repo-update
# Priority 90 beats the default 99: our packages win over Tumbleweed's.
# Release ISO: tested packages from :release; test/live images: :devel
if has_profile release; then
  zypper --non-interactive addrepo -f -p 90 \
    https://download.opensuse.org/repositories/home:/Tokajer:/nazoos:/release/openSUSE_Tumbleweed/ nazoos
else
  zypper --non-interactive addrepo -f -p 90 \
    https://download.opensuse.org/repositories/home:/Tokajer:/nazoos:/devel/openSUSE_Tumbleweed/ nazoos-devel
fi
