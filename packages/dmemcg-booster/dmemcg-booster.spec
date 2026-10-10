# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is not in Tumbleweed
# (ADR 0013, notes/vram.md in NazoOS-dev). Source0 is downloaded by the
# OBS service download_files, vendor.tar.zst made by cargo_vendor.
# On a version update: change Version and the src parameter in _service.

Name:           dmemcg-booster
Version:        0.1.3
Release:        0
Summary:        Keeps VRAM of the foreground game protected via the dmem cgroup
License:        MIT
URL:            https://gitlab.steamos.cloud/holo/dmemcg-booster
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.gz
Source1:        vendor.tar.zst
BuildRequires:  cargo-packaging
BuildRequires:  zstd
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(systemd)
# Sets the protection; plasma-foreground-booster decides which app gets it
Recommends:     plasma-foreground-booster
ExclusiveArch:  %{rust_tier1_arches}

%description
dmemcg-booster enables the dmem cgroup controller (device memory, i.e.
VRAM) along the cgroup tree and sets dmem.low, so applications in the
user's app.slice are protected from having their VRAM evicted by other
processes. Together with plasma-foreground-booster the focused game
keeps its buffers in VRAM instead of spilling into slower system
memory. Works best with kernel-nazoos (TTM eviction patches); on other
kernels the plain dmem protection applies.

A system service handles the root-owned cgroups, a user service the
cgroups of the graphical session.

%prep
%autosetup -a1

%build
%{cargo_build}

%install
install -Dm0755 target/release/%{name} %{buildroot}%{_bindir}/%{name}
install -Dm0644 %{name}-system.service %{buildroot}%{_unitdir}/%{name}-system.service
install -Dm0644 %{name}-user.service %{buildroot}%{_userunitdir}/%{name}-user.service
# Enabled by default on NazoOS. The presets live in this package (not in
# nazoos-tweaks) so they are present when %%post evaluates them
install -dm0755 %{buildroot}%{_presetdir} %{buildroot}%{_userpresetdir}
echo "enable %{name}-system.service" > %{buildroot}%{_presetdir}/80-%{name}.preset
echo "enable %{name}-user.service" > %{buildroot}%{_userpresetdir}/80-%{name}.preset

%pre
%service_add_pre %{name}-system.service

%post
%service_add_post %{name}-system.service
%systemd_user_post %{name}-user.service

%preun
%service_del_preun %{name}-system.service
%systemd_user_preun %{name}-user.service

%postun
%service_del_postun %{name}-system.service
%systemd_user_postun %{name}-user.service

%files
%license LICENSE
%{_bindir}/%{name}
%{_unitdir}/%{name}-system.service
%{_userunitdir}/%{name}-user.service
%{_presetdir}/80-%{name}.preset
%{_userpresetdir}/80-%{name}.preset

%changelog
