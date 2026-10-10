# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is not in Tumbleweed
# (notes/btrfs-assistant.md in NazoOS-dev). The source tarball is
# downloaded by the OBS service download_files from the Source0 URL.

Name:           btrfs-assistant
Version:        2.3.2
Release:        0
Summary:        GUI management tool for Btrfs file systems and Snapper
License:        GPL-3.0-only
URL:            https://gitlab.com/btrfs-assistant/btrfs-assistant
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.gz
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hicolor-icon-theme
BuildRequires:  libbtrfsutil-devel
BuildRequires:  cmake(Qt6LinguistTools)
BuildRequires:  cmake(Qt6Widgets)
# Called at runtime by path, not linked
Requires:       btrfsprogs
Requires:       polkit
Requires:       snapper
Recommends:     btrfsmaintenance
Recommends:     %{name}-lang

%description
Btrfs Assistant is a graphical tool for Btrfs file systems: overview
of the file system, subvolumes, scrub and balance, a front-end for
Snapper (browse, create, delete and restore snapshots, restore single
files) and for btrfsmaintenance.

%lang_package

%prep
%autosetup -p1
# Fixed interpreter instead of /usr/bin/env (openSUSE packaging rule)
sed -i '1s|^#!.*|#!/usr/bin/bash|' src/btrfs-assistant src/btrfs-assistant-launcher
# openSUSE keeps the btrfsmaintenance settings in sysconfig
sed -i 's|^bm_config = .*|bm_config = /etc/sysconfig/btrfsmaintenance|' \
  src/btrfs-assistant.conf

%build
%cmake -DCMAKE_BUILD_TYPE=Release
%cmake_build

%install
%cmake_install
%find_lang btrfsassistant --with-qt

%files
%license LICENSE
%doc README.md changelog
%{_bindir}/btrfs-assistant
%{_bindir}/btrfs-assistant-bin
%{_bindir}/btrfs-assistant-launcher
%config(noreplace) %{_sysconfdir}/btrfs-assistant.conf
%{_datadir}/applications/btrfs-assistant.desktop
%{_datadir}/metainfo/btrfs-assistant.metainfo.xml
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/actions
%{_datadir}/polkit-1/actions/org.btrfs-assistant.pkexec.policy
%{_datadir}/icons/hicolor/scalable/apps/btrfs-assistant.svg

%files lang -f btrfsassistant.lang
%dir %{_datadir}/btrfs-assistant
%dir %{_datadir}/btrfs-assistant/translations

%changelog
