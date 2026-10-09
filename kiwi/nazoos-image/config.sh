#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Runs by KIWI inside the image root after all packages are installed.
# Docs: https://osinside.github.io/kiwi/concept_and_workflow/shell_scripts.html

set -euxo pipefail

# KIWI writes the image settings (e.g. kiwi_profiles) into /.profile
test -f /.profile && . /.profile
profile=${kiwi_profiles:-}

echo nazoos > /etc/hostname

# Services
systemctl set-default graphical.target
# No "enable sddm": Tumbleweed starts it via display-manager-legacy.service,
# sddm-qt6 registers itself through update-alternatives
systemctl enable NetworkManager.service
# wicked would fight NetworkManager over the interfaces
systemctl disable wicked.service || true
systemctl enable snapper-timeline.timer snapper-cleanup.timer
# Apply our presets (nazoos-tweaks) again: in the image build a service
# package may be installed before the preset file exists
systemctl preset coolercontrold.service

if [ "$profile" = test ]; then
  # Test image only: ssh into the VM (test password!).
  # qemu-guest-agent needs no enable, udev starts it when the VM has the channel
  systemctl enable sshd.service
fi

if [ "$profile" = live ]; then
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
fi

# Online repos for the finished system; the OBS build repos are not kept
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/tumbleweed/repo/oss/ repo-oss
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/tumbleweed/repo/non-oss/ repo-non-oss
zypper --non-interactive addrepo -f \
  https://download.opensuse.org/update/tumbleweed/ repo-update
# Priority 90 beats the default 99: our packages win over Tumbleweed's
zypper --non-interactive addrepo -f -p 90 \
  https://download.opensuse.org/repositories/home:/Tokajer:/nazoos:/devel/openSUSE_Tumbleweed/ nazoos-devel
