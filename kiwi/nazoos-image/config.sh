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

# SDDM greeter on Wayland (kwin) instead of Xorg
# TODO: move into a NazoOS package so Calamares installs get it too
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-nazoos-wayland.conf <<'EOF'
[General]
DisplayServer=wayland
GreeterEnvironment=QT_WAYLAND_SHELL_INTEGRATION=layer-shell

[Wayland]
CompositorCommand=kwin_wayland --drm --no-lockscreen --no-global-shortcuts --locale1
EOF

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
