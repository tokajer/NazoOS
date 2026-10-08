# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-calamares-config
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Calamares installer configuration for NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
Requires:       calamares
# Satisfies "Requires: calamares-branding >= 3" of the calamares package
Provides:       calamares-branding = 3
Conflicts:      calamares-branding-upstream
Requires:       nazoos-branding
# Used by the post-install script inside the installed system
Requires:       btrfsprogs
Requires:       dracut
Requires:       grub2-snapper-plugin
Requires:       grub2-x86_64-efi
Requires:       perl-Bootloader
Requires:       shim
Requires:       snapper
Requires:       util-linux
# Live session: installer starter runs Calamares via sudo
Requires:       sudo

%description
Configuration and branding for the Calamares installer on the NazoOS
live medium: btrfs with the openSUSE subvolume layout, Snapper, GRUB
with Secure Boot (shim) and snapshot boot entries.
Also sets up the live session: autologin into Plasma and an installer
starter (menu + autostart).
Only for the live medium; it removes itself from the installed system.

%prep
%autosetup

%build
# Nothing to compile

%install
install -Dm0644 settings.conf %{buildroot}%{_datadir}/calamares/settings.conf
install -Dm0644 -t %{buildroot}%{_datadir}/calamares/modules modules/*.conf
install -Dm0644 -t %{buildroot}%{_datadir}/calamares/branding/nazoos \
  branding/nazoos/branding.desc branding/nazoos/show.qml
install -Dm0755 scripts/nazoos-postinstall \
  %{buildroot}%{_libexecdir}/nazoos-calamares/nazoos-postinstall
# Live session
install -Dm0644 live/nazoos-installer.desktop \
  %{buildroot}%{_datadir}/applications/nazoos-installer.desktop
install -Dm0644 live/nazoos-installer.desktop \
  %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-installer.desktop
install -Dm0440 live/sudoers %{buildroot}%{_sysconfdir}/sudoers.d/nazoos-live
install -Dm0644 live/50-nazoos-live.conf \
  %{buildroot}%{_prefix}/lib/sddm/sddm.conf.d/50-nazoos-live.conf

%files
%dir %{_datadir}/calamares
%{_datadir}/calamares/settings.conf
%{_datadir}/calamares/modules
%{_datadir}/calamares/branding
%{_libexecdir}/nazoos-calamares
%{_datadir}/applications/nazoos-installer.desktop
%dir %{_sysconfdir}/xdg/autostart
%config %{_sysconfdir}/xdg/autostart/nazoos-installer.desktop
%dir %{_sysconfdir}/sudoers.d
%config %{_sysconfdir}/sudoers.d/nazoos-live
%dir %{_prefix}/lib/sddm
%dir %{_prefix}/lib/sddm/sddm.conf.d
%{_prefix}/lib/sddm/sddm.conf.d/50-nazoos-live.conf

%changelog
