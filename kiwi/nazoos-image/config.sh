#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Runs by KIWI inside the image root after all packages are installed.
# Docs: https://osinside.github.io/kiwi/concept_and_workflow/shell_scripts.html

set -euxo pipefail

echo nazoos > /etc/hostname

# Services
systemctl set-default graphical.target
# No "enable sddm": Tumbleweed starts it via display-manager-legacy.service,
# sddm-qt6 registers itself through update-alternatives
systemctl enable NetworkManager.service
# wicked would fight NetworkManager over the interfaces
systemctl disable wicked.service || true
systemctl enable snapper-timeline.timer snapper-cleanup.timer
# Test image only: ssh into the VM (test password!); drop for releases.
# qemu-guest-agent needs no enable, udev starts it when the VM has the channel
systemctl enable sshd.service

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
