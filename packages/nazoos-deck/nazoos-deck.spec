# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-deck
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        NazoOS handheld support (Steam Deck, ROG Ally, Legion Go, ...)
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  desktop-file-utils
BuildRequires:  systemd-rpm-macros
BuildArch:      noarch
# Pattern metadata, read by zypper, YaST and KIWI
Provides:       pattern() = nazoos-deck
Provides:       pattern-category() = NazoOS
Provides:       pattern-icon() = pattern-games
Provides:       pattern-order() = 1010
Provides:       pattern-visible()
# Steam gaming mode + switching (boot mode is set by installer/Welcome)
Requires:       nazoos-session
Requires:       systemd
# First login: xdg-user-dir, kwriteconfig6
Requires:       xdg-user-dirs
Requires:       kf6-kconfig
# Controllers, buttons and gyro of ROG Ally, Legion Go, MSI Claw, AYANEO,
# GPD, OneXPlayer, Zotac Zone, ... (started by udev on those devices)
Recommends:     inputplumber
# Steam Deck: fan curve, speaker/microphone DSP, OLED panel correction,
# power button. Not jupiter-dock-updater-bin: its install script
# downloads Valve's proprietary dock updater (no network in the OBS
# image build); opt-in card in NazoOS Welcome → Gaming instead
Recommends:     jupiter-fan-control
Recommends:     steamdeck-dsp
Recommends:     galileo-mura
Recommends:     steamos-powerbuttond
# Desktop mode on a touch screen: on-screen keyboard, auto-rotation
Recommends:     maliit-keyboard
Recommends:     iio-sensor-proxy
%{?systemd_ordering}

%description
Support for gaming handhelds: Steam's gaming mode at startup (set by the
installer or in NazoOS Welcome), controller support through InputPlumber,
and for the Steam Deck Valve's fan control, audio DSP, OLED panel
correction and power button handling. Desktop mode gets an on-screen
keyboard and screen rotation, and a "Gaming Mode" shortcut on the desktop.

%prep
%autosetup

%build
# Nothing to compile

%install
for u in jupiter-fan-control pipewire-sysconf wireplumber-sysconf; do
  install -Dm0644 systemd/50-nazoos-steam-deck-only.conf \
    %{buildroot}%{_unitdir}/$u.service.d/50-nazoos-steam-deck-only.conf
done
install -Dm0644 systemd/90-nazoos-deck.preset \
  %{buildroot}%{_presetdir}/90-nazoos-deck.preset
install -Dm0644 systemd/90-nazoos-deck-user.preset \
  %{buildroot}%{_userpresetdir}/90-nazoos-deck.preset
install -Dm0755 session/nazoos-deck-firstlogin \
  %{buildroot}%{_libexecdir}/nazoos-deck/nazoos-deck-firstlogin
install -Dm0644 session/nazoos-deck-firstlogin.desktop \
  %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-deck-firstlogin.desktop

%check
desktop-file-validate %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-deck-firstlogin.desktop
bash -n session/nazoos-deck-firstlogin

%posttrans
# The services come from other packages, which may be installed before
# this preset exists; apply it once everything is in place
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl preset jupiter-fan-control.service pipewire-sysconf.service \
  wireplumber-sysconf.service >/dev/null 2>&1 || :
systemctl --global preset steamos-powerbuttond.service >/dev/null 2>&1 || :

%files
%dir %{_unitdir}/jupiter-fan-control.service.d
%dir %{_unitdir}/pipewire-sysconf.service.d
%dir %{_unitdir}/wireplumber-sysconf.service.d
%{_unitdir}/*.service.d/50-nazoos-steam-deck-only.conf
%{_presetdir}/90-nazoos-deck.preset
%dir %{_userpresetdir}
%{_userpresetdir}/90-nazoos-deck.preset
%{_libexecdir}/nazoos-deck
%dir %{_sysconfdir}/xdg/autostart
%config %{_sysconfdir}/xdg/autostart/nazoos-deck-firstlogin.desktop

%changelog
