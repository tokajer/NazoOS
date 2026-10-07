# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-branding
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        NazoOS desktop branding and defaults
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
Requires:       breeze6-cursors
Requires:       breeze6-style
Requires:       kf6-breeze-icons
Requires:       plasma6-workspace
# Login screen theme; plasma6-branding-openSUSE pulled it in before
Requires:       (plasma6-sddm-theme-openSUSE if sddm)
# Both ship /etc/xdg/kdeglobals; ours replaces openSUSE's Plasma defaults
Conflicts:      plasma6-branding-openSUSE

%description
Desktop defaults for NazoOS: the NazoOS global theme for KDE Plasma
(Breeze Dark with the NazoOS wallpaper, also on the lock and login
screen), Breeze cursors (also as system default cursor theme), the
NazoOS website in System Settings, tearing allowed for fullscreen games
and file indexing limited to file names.

%prep
%autosetup

%build
# Nothing to compile

%install
install -Dm0644 -t %{buildroot}%{_sysconfdir}/xdg \
  xdg/kdeglobals xdg/kcminputrc xdg/kcm-about-distrorc xdg/kscreenlockerrc \
  xdg/kwinrc xdg/baloofilerc
install -Dm0644 -t %{buildroot}%{_datadir}/wallpapers/NazoOS wallpaper/NazoOS/metadata.json
install -Dm0644 -t %{buildroot}%{_datadir}/wallpapers/NazoOS/contents/images \
  wallpaper/NazoOS/contents/images/*.png
install -Dm0644 -t %{buildroot}%{_datadir}/plasma/look-and-feel/org.nazoos.desktop \
  look-and-feel/org.nazoos.desktop/metadata.json
install -Dm0644 -t %{buildroot}%{_datadir}/plasma/look-and-feel/org.nazoos.desktop/contents \
  look-and-feel/org.nazoos.desktop/contents/defaults
install -Dm0644 sddm/theme.conf.user \
  %{buildroot}%{_datadir}/sddm/themes/breeze-openSUSE/theme.conf.user
install -Dm0644 icons/index.theme %{buildroot}%{_datadir}/icons/default/index.theme

%files
%config(noreplace) %{_sysconfdir}/xdg/kdeglobals
%config(noreplace) %{_sysconfdir}/xdg/kcminputrc
%config(noreplace) %{_sysconfdir}/xdg/kcm-about-distrorc
%config(noreplace) %{_sysconfdir}/xdg/kscreenlockerrc
%config(noreplace) %{_sysconfdir}/xdg/kwinrc
%config(noreplace) %{_sysconfdir}/xdg/baloofilerc
%dir %{_datadir}/wallpapers
%{_datadir}/wallpapers/NazoOS
%dir %{_datadir}/plasma
%dir %{_datadir}/plasma/look-and-feel
%{_datadir}/plasma/look-and-feel/org.nazoos.desktop
%dir %{_datadir}/sddm
%dir %{_datadir}/sddm/themes
%dir %{_datadir}/sddm/themes/breeze-openSUSE
%{_datadir}/sddm/themes/breeze-openSUSE/theme.conf.user
%dir %{_datadir}/icons/default
%{_datadir}/icons/default/index.theme

%changelog
