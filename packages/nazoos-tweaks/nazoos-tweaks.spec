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

%description
Default kernel parameters (sysctl) tuned for gaming and desktop
responsiveness on NazoOS.

%prep
%autosetup

%build
# Nothing to compile

%install
install -Dm0644 sysctl.d/70-nazoos.conf %{buildroot}%{_sysctldir}/70-nazoos.conf

%post
%sysctl_apply 70-nazoos.conf

%files
%{_sysctldir}/70-nazoos.conf

%changelog
