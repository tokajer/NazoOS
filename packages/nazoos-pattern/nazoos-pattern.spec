# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-pattern
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        NazoOS Gaming Desktop
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
BuildArch:      noarch
# Pattern metadata, read by zypper, YaST and KIWI
Provides:       pattern() = nazoos
Provides:       pattern-category() = NazoOS
Provides:       pattern-icon() = pattern-games
Provides:       pattern-order() = 1000
Provides:       pattern-visible()
# Core: removing it would remove the pattern
Requires:       nazoos-tweaks
Requires:       nazoos-branding
# Fallback: older Calamares configs wrote classic console keymap names;
# Tumbleweed's kbd only ships XKB-generated ones, the rest is in kbd-legacy
Requires:       kbd-legacy
# setfacl: udev rules (e.g. ddcutil i2c) grant device access via ACLs
Requires:       acl
# Apps and extras: installed by default, but users may remove them
# Gaming
Recommends:     steam
Recommends:     steam-devices
Recommends:     lutris
Recommends:     gamemode
Recommends:     mangohud
Recommends:     gamescope
Recommends:     wine
Recommends:     protontricks
Recommends:     winetricks
Recommends:     goverlay
# Hardware
Recommends:     OpenRGB
Recommends:     lact
Recommends:     coolercontrol
Recommends:     fwupd
Recommends:     power-profiles-daemon
# Scheduler, toggled by nazoos-welcome (ADR 0002)
Recommends:     scx
# Audio
Recommends:     pipewire-config-upmix
Recommends:     rtkit
# First steps after installation (drivers, codecs, apps)
Recommends:     nazoos-welcome
# Software management
Recommends:     discover6
Recommends:     discover6-backend-flatpak
Recommends:     flatpak
Recommends:     flatpak-remote-flathub
Recommends:     myrlyn
# Desktop
Recommends:     MozillaFirefox
Recommends:     kate

%description
Installs the NazoOS gaming desktop: system tweaks, Steam, Lutris,
Wine, Gamescope, MangoHud, GameMode, hardware tools and graphical
software management (Discover with Flatpak, Myrlyn).

%prep
# Nothing to unpack: a pattern only carries dependencies

%build
# Nothing to compile

%install
# A pattern needs at least one file, otherwise the RPM is empty
mkdir -p %{buildroot}%{_docdir}/patterns
echo 'This file marks the pattern nazoos to be installed.' \
  > %{buildroot}%{_docdir}/patterns/nazoos.txt

%files
%dir %{_docdir}/patterns
%{_docdir}/patterns/nazoos.txt

%changelog
