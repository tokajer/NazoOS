# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-tweaks
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        System tweaks for gaming performance on NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  systemd-rpm-macros
BuildArch:      noarch
Requires:       zram-generator

%description
Default kernel parameters (sysctl), zram swap configuration,
udev rules (I/O schedulers, audio and SATA power management) and
ntsync module loading for Wine/Proton, tuned for gaming and
desktop responsiveness on NazoOS.

%prep
%autosetup

%build
# Nothing to compile

%install
install -Dm0644 sysctl.d/70-nazoos.conf %{buildroot}%{_sysctldir}/70-nazoos.conf
install -Dm0644 zram-generator.conf.d/70-nazoos.conf \
  %{buildroot}%{_prefix}/lib/systemd/zram-generator.conf.d/70-nazoos.conf
install -Dm0644 tmpfiles.d/70-nazoos.conf %{buildroot}%{_tmpfilesdir}/nazoos-tweaks.conf
install -Dm0644 -t %{buildroot}%{_udevrulesdir} udev/*.rules
install -Dm0644 modules-load.d/ntsync.conf %{buildroot}%{_modulesloaddir}/nazoos-ntsync.conf

%post
%sysctl_apply 70-nazoos.conf
%tmpfiles_create nazoos-tweaks.conf
%udev_rules_update

%files
%{_sysctldir}/70-nazoos.conf
%dir %{_prefix}/lib/systemd/zram-generator.conf.d
%{_prefix}/lib/systemd/zram-generator.conf.d/70-nazoos.conf
%{_tmpfilesdir}/nazoos-tweaks.conf
%{_udevrulesdir}/*-nazoos-*.rules
%{_modulesloaddir}/nazoos-ntsync.conf

%changelog
