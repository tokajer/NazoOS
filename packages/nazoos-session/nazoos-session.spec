# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-session
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Steam gaming mode session for NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  desktop-file-utils
BuildRequires:  systemd-rpm-macros
BuildArch:      noarch
# Gamescope + Steam's gamepad UI as a Wayland session (ChimeraOS scripts)
Requires:       gamescope
Requires:       gamescope-session-plus
Requires:       gamescope-session-steam
# steamos-session-select and the steamos-polkit-helpers stubs Steam calls
# in gaming mode; its steamos-session-select calls our os-session-select
Requires:       gamescope-session-steam-generic
# Same SDDM build as the image (sddm-qt6 also provides "sddm")
Requires:       sddm-qt6
Requires:       polkit
Requires:       systemd
# dbus-send: log out of Plasma when switching
Requires:       dbus-1-tools
Requires:       util-linux
Recommends:     steam
# Performance overlay in gaming mode (Steam's "Performance" menu)
Recommends:     mangoapp
Recommends:     libnotify-tools
%{?systemd_ordering}

%description
Steam's gaming mode (the Steam Deck interface in Gamescope) as a session
on the login screen of every NazoOS system, plus switching between
gaming mode and the Plasma desktop with one click: the "Gaming Mode"
menu entry, and "Switch to Desktop" in Steam.
In boot mode "gaming" (handhelds, living room PCs; set in NazoOS Welcome
or by the installer) the computer logs into gaming mode automatically,
and the desktop is used for one session only.

%prep
%autosetup

%build
# Nothing to compile

%install
install -Dm0755 bin/nazoos-session-select %{buildroot}%{_bindir}/nazoos-session-select
install -Dm0755 -t %{buildroot}%{_libexecdir}/nazoos-session \
  libexec/nazoos-session-ctl libexec/nazoos-session-switch \
  libexec/nazoos-detect-handheld
# Hook path fixed by gamescope-session-steam-generic
install -Dm0755 libexec/os-session-select %{buildroot}%{_prefix}/lib/os-session-select
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-session/wayland-sessions \
  data/wayland-sessions/*.desktop
install -Dm0644 data/40-nazoos-session.conf \
  %{buildroot}%{_prefix}/lib/sddm/sddm.conf.d/40-nazoos-session.conf
install -Dm0644 data/org.nazoos.session.policy \
  %{buildroot}%{_datadir}/polkit-1/actions/org.nazoos.session.policy
install -Dm0644 data/org.nazoos.session.gaming.desktop \
  %{buildroot}%{_datadir}/applications/org.nazoos.session.gaming.desktop
install -Dm0644 data/nazoos-session-boot.service \
  %{buildroot}%{_unitdir}/nazoos-session-boot.service
install -Dm0644 -t %{buildroot}%{_userunitdir} \
  data/nazoos-session-gaming.service data/nazoos-session-desktop.service
install -Dm0644 data/90-nazoos-session.preset \
  %{buildroot}%{_presetdir}/90-nazoos-session.preset
install -Dm0644 data/90-nazoos-session-user.preset \
  %{buildroot}%{_userpresetdir}/90-nazoos-session.preset
install -d %{buildroot}%{_sysconfdir}/nazoos

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.nazoos.session.gaming.desktop
for f in bin/nazoos-session-select libexec/*; do bash -n "$f"; done

%pre
%service_add_pre nazoos-session-boot.service

%post
%service_add_post nazoos-session-boot.service
%systemd_user_post nazoos-session-gaming.service nazoos-session-desktop.service

%preun
%service_del_preun nazoos-session-boot.service
%systemd_user_preun nazoos-session-gaming.service nazoos-session-desktop.service
# Last removal: no automatic login into a session that is gone
if [ $1 -eq 0 ] && [ -x %{_libexecdir}/nazoos-session/nazoos-session-ctl ]; then
  %{_libexecdir}/nazoos-session/nazoos-session-ctl boot-mode desktop || :
fi

%postun
%service_del_postun nazoos-session-boot.service
%systemd_user_postun nazoos-session-gaming.service nazoos-session-desktop.service

%files
%{_bindir}/nazoos-session-select
%{_libexecdir}/nazoos-session
%{_prefix}/lib/os-session-select
%{_datadir}/nazoos-session
%dir %{_prefix}/lib/sddm
%dir %{_prefix}/lib/sddm/sddm.conf.d
%{_prefix}/lib/sddm/sddm.conf.d/40-nazoos-session.conf
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/actions
%{_datadir}/polkit-1/actions/org.nazoos.session.policy
%{_datadir}/applications/org.nazoos.session.gaming.desktop
%{_unitdir}/nazoos-session-boot.service
%{_userunitdir}/nazoos-session-gaming.service
%{_userunitdir}/nazoos-session-desktop.service
%{_presetdir}/90-nazoos-session.preset
%dir %{_userpresetdir}
%{_userpresetdir}/90-nazoos-session.preset
%dir %{_sysconfdir}/nazoos
# Written by nazoos-session-ctl
%ghost %config(noreplace) %{_sysconfdir}/nazoos/session.conf
%ghost %{_sysconfdir}/nazoos/session-oneshot
# Owned by sddm too; sddm is not in the build root, so the OBS file
# list check would call it unowned
%dir %{_sysconfdir}/sddm.conf.d
%ghost %config(noreplace) %{_sysconfdir}/sddm.conf.d/zz-nazoos-session.conf

%changelog
