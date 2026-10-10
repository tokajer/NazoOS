# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is not in Tumbleweed
# (ADR 0013, notes/vram.md in NazoOS-dev). Both sources come from Natalie
# Vock's fork of KDE's kcgroups (two branches, same commits as CachyOS):
#   Source0: branch dmemcg                    - the kcgroups library
#   Source1: branch dmemcg-foreground-booster - the booster
# kcgroups is linked statically: nothing else uses it, so there is no
# shared library package to maintain. Sources downloaded by download_files.

%global kcgroups_commit d106f1c8f44c1f231a9050b2bf82a34bb7d5db32
%global booster_commit  386ccfe529dac54fca51e24aec4b880a31afe836

Name:           plasma-foreground-booster
Version:        0~git20260408.386ccfe
Release:        0
Summary:        Gives the focused Plasma window more CPU weight and VRAM protection
License:        LGPL-2.1-or-later
URL:            https://github.com/pixelcluster/kcgroups
Source0:        %{url}/archive/%{kcgroups_commit}/kcgroups-%{kcgroups_commit}.tar.gz
Source1:        %{url}/archive/%{booster_commit}/kcgroups-%{booster_commit}.tar.gz
BuildRequires:  cmake
BuildRequires:  extra-cmake-modules
BuildRequires:  gcc-c++
BuildRequires:  cmake(KF6Config)
BuildRequires:  cmake(KF6DBusAddons)
BuildRequires:  cmake(LibTaskManager)
BuildRequires:  cmake(Qt6DBus)
BuildRequires:  pkgconfig(systemd)
# plasma-workspace.target already has Wants=plasma-foreground-booster.service
Requires:       plasma6-workspace
# Sets dmem.low on the system side; without it only the CPU weight works
Recommends:     dmemcg-booster

%description
plasma-foreground-booster watches the active window in KDE Plasma and
moves the application it belongs to up: higher CPU weight and, with
dmemcg-booster and kernel-nazoos, VRAM protection (dmem.low), so a
fullscreen game keeps its VRAM when other programs need some.

Started by plasma-workspace.target. It can be switched off in
~/.config/kcgroupsrc: [Foreground Booster] autostart=false.

%prep
%setup -q -c -T -a0 -a1

%build
# 1. kcgroups as a static library, installed into the build tree only
pushd kcgroups-%{kcgroups_commit}
cmake -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_WITH_QT6=ON \
  -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_CXX_FLAGS="%{optflags}" -DCMAKE_INSTALL_PREFIX=%{_prefix}
cmake --build build %{?_smp_mflags}
DESTDIR=$PWD/../kcgroups-root cmake --install build
popd
# 2. the booster against it
pushd kcgroups-%{booster_commit}
cmake -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTING=OFF \
  -DCMAKE_CXX_FLAGS="%{optflags}" -DCMAKE_INSTALL_PREFIX=%{_prefix} \
  -DCMAKE_PREFIX_PATH=$PWD/../kcgroups-root%{_prefix}
cmake --build build %{?_smp_mflags}
popd

%install
DESTDIR=%{buildroot} cmake --install kcgroups-%{booster_commit}/build
# The autostart copy only starts when kcgroupsrc says autostart=false
# (upstream fallback for sessions without systemd); Plasma on Tumbleweed
# starts the systemd unit, so the copy is not needed
rm %{buildroot}%{_sysconfdir}/xdg/autostart/org.kde.foreground-booster.desktop

%post
%systemd_user_post %{name}.service

%preun
%systemd_user_preun %{name}.service

%postun
%systemd_user_postun %{name}.service

%files
%license kcgroups-%{kcgroups_commit}/LICENSES/LGPL-2.1-or-later.txt
%{_bindir}/foreground_booster
%{_userunitdir}/%{name}.service
# KWin only grants the window management protocol to clients whose
# .desktop file lists it (X-KDE-Wayland-Interfaces)
%{_datadir}/applications/org.kde.foreground-booster.desktop

%changelog
