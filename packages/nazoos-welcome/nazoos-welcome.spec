# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-welcome
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        First steps after installing NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  desktop-file-utils
BuildRequires:  gettext-tools
BuildRequires:  python3
BuildArch:      noarch
# GUI: Python + Qt Quick + Kirigami, native Plasma look
Requires:       kf6-kirigami-imports
Requires:       kf6-qqc2-desktop-style
Requires:       python3
Requires:       python3-pyside6
Requires:       qt6-declarative-imports
# Root actions via pkexec + our Polkit policy
Requires:       polkit
# System probes (lspci, lsblk/findmnt) and actions
Requires:       pciutils
Requires:       util-linux
Requires:       zypper
Recommends:     flatpak
Recommends:     nazoos-branding
Recommends:     snapper

%description
NazoOS Welcome sets up a fresh NazoOS installation without a terminal:
NVIDIA driver, multimedia codecs from Packman, sched_ext scheduler,
kernel options, optional apps from Flathub, automatic mounting of extra
drives, system services, updates, snapshots and maintenance.
Root actions run through a small helper started with pkexec, which
only accepts a fixed list of actions.

%prep
%autosetup

%build
for po in po/*.po; do
  lang=$(basename "$po" .po)
  mkdir -p "locale/$lang/LC_MESSAGES"
  msgfmt --check -o "locale/$lang/LC_MESSAGES/%{name}.mo" "$po"
done

%install
install -Dm0755 nazoos-welcome %{buildroot}%{_bindir}/nazoos-welcome
install -Dm0755 helper/nazoos-welcome-helper \
  %{buildroot}%{_libexecdir}/nazoos-welcome/nazoos-welcome-helper
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/nazoos_welcome \
  nazoos_welcome/*.py
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml qml/*.qml
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml/components \
  qml/components/*.qml
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml/pages \
  qml/pages/*.qml
install -Dm0644 data/org.nazoos.welcome.desktop \
  %{buildroot}%{_datadir}/applications/org.nazoos.welcome.desktop
install -Dm0644 data/nazoos-welcome-autostart.desktop \
  %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
install -Dm0644 data/org.nazoos.welcome.policy \
  %{buildroot}%{_datadir}/polkit-1/actions/org.nazoos.welcome.policy
cp -a locale %{buildroot}%{_datadir}/
# Byte-compile at build time: users cannot write __pycache__ below /usr
python3 -m compileall -q --invalidation-mode checked-hash \
  -d %{_datadir}/nazoos-welcome/nazoos_welcome \
  %{buildroot}%{_datadir}/nazoos-welcome/nazoos_welcome
%find_lang %{name}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.nazoos.welcome.desktop
desktop-file-validate %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" helper/nazoos-welcome-helper

%files -f %{name}.lang
%{_bindir}/nazoos-welcome
%dir %{_libexecdir}/nazoos-welcome
%{_libexecdir}/nazoos-welcome/nazoos-welcome-helper
%{_datadir}/nazoos-welcome
%{_datadir}/applications/org.nazoos.welcome.desktop
%config(noreplace) %{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/actions
%{_datadir}/polkit-1/actions/org.nazoos.welcome.policy

%changelog
