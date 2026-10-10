# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-update
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Graphical system updates and rollback for NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  desktop-file-utils
BuildRequires:  gettext-tools
BuildRequires:  python3
BuildRequires:  systemd-rpm-macros
BuildArch:      noarch
# GUI: Python + Qt Quick + Kirigami, like nazoos-welcome
Requires:       kf6-kirigami-imports
Requires:       kf6-qqc2-desktop-style
Requires:       python3
Requires:       python3-pyside6
Requires:       qt6-declarative-imports
# Notifications with an "Update now" button
Requires:       libnotify-tools
Requires:       polkit
Requires:       snapper
# Snapshot pair before and after every zypper run
Requires:       snapper-zypp-plugin
Requires:       util-linux
Requires:       zypper
Recommends:     btrfs-assistant
Recommends:     flatpak
Recommends:     grub2-snapper-plugin
Recommends:     myrlyn
%{?systemd_ordering}

%description
NazoOS Update checks for system and Flatpak updates in the background,
shows a notification with an "Update now" button and installs updates
with "zypper dist-upgrade" behind a password dialog. Snapper takes a
snapshot before every update. After starting an older snapshot from
the boot menu it offers to make that state permanent (snapper rollback).

%prep
%autosetup

%build
for po in po/*.po; do
  lang=$(basename "$po" .po)
  mkdir -p "locale/$lang/LC_MESSAGES"
  msgfmt --check -o "locale/$lang/LC_MESSAGES/%{name}.mo" "$po"
done

%install
install -Dm0755 nazoos-update %{buildroot}%{_bindir}/nazoos-update
install -Dm0755 helper/nazoos-update-helper \
  %{buildroot}%{_libexecdir}/nazoos-update/nazoos-update-helper
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-update/nazoos_update \
  nazoos_update/*.py
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-update/qml qml/*.qml
install -Dm0644 data/org.nazoos.update.desktop \
  %{buildroot}%{_datadir}/applications/org.nazoos.update.desktop
install -Dm0644 data/org.nazoos.update.policy \
  %{buildroot}%{_datadir}/polkit-1/actions/org.nazoos.update.policy
install -Dm0644 -t %{buildroot}%{_unitdir} \
  data/nazoos-update-check.service data/nazoos-update-check.timer
install -Dm0644 -t %{buildroot}%{_userunitdir} \
  data/nazoos-update-notify.service data/nazoos-update-notify.timer
install -Dm0644 data/90-nazoos-update.preset \
  %{buildroot}%{_presetdir}/90-nazoos-update.preset
install -Dm0644 data/90-nazoos-update-user.preset \
  %{buildroot}%{_userpresetdir}/90-nazoos-update.preset
install -Dm0644 data/PlasmaDiscoverUpdates \
  %{buildroot}%{_sysconfdir}/xdg/PlasmaDiscoverUpdates
install -d %{buildroot}%{_localstatedir}/lib/nazoos-update
cp -a locale %{buildroot}%{_datadir}/
python3 -m compileall -q --invalidation-mode checked-hash \
  -d %{_datadir}/nazoos-update/nazoos_update \
  %{buildroot}%{_datadir}/nazoos-update/nazoos_update
%find_lang %{name}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.nazoos.update.desktop
python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" helper/nazoos-update-helper

%pre
%service_add_pre nazoos-update-check.service nazoos-update-check.timer

%post
%service_add_post nazoos-update-check.service nazoos-update-check.timer
%systemd_user_post nazoos-update-notify.service nazoos-update-notify.timer

%preun
%service_del_preun nazoos-update-check.service nazoos-update-check.timer
%systemd_user_preun nazoos-update-notify.service nazoos-update-notify.timer

%postun
%service_del_postun nazoos-update-check.service nazoos-update-check.timer
%systemd_user_postun nazoos-update-notify.service nazoos-update-notify.timer

%files -f %{name}.lang
%{_bindir}/nazoos-update
%dir %{_libexecdir}/nazoos-update
%{_libexecdir}/nazoos-update/nazoos-update-helper
%{_datadir}/nazoos-update
%{_datadir}/applications/org.nazoos.update.desktop
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/actions
%{_datadir}/polkit-1/actions/org.nazoos.update.policy
%{_unitdir}/nazoos-update-check.service
%{_unitdir}/nazoos-update-check.timer
%{_userunitdir}/nazoos-update-notify.service
%{_userunitdir}/nazoos-update-notify.timer
%{_presetdir}/90-nazoos-update.preset
%dir %{_userpresetdir}
%{_userpresetdir}/90-nazoos-update.preset
%config(noreplace) %{_sysconfdir}/xdg/PlasmaDiscoverUpdates
%dir %{_localstatedir}/lib/nazoos-update
%ghost %{_localstatedir}/lib/nazoos-update/status.json

%changelog
