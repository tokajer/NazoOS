# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Stage 2 of the NazoOS kernel opt-in (ADR 0008): installed by
# nazoos-welcome after 3 clean starts of kernel-nazoos. The conflicts keep
# kernel-default and its module packages away, also on "zypper dup".
# Removing this package (button "Back to openSUSE kernel") lifts the block.

Name:           nazoos-kernel-only
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Use only the NazoOS kernel, block the openSUSE kernel
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
BuildArch:      noarch
Requires:       kernel-nazoos
Conflicts:      kernel-default
Conflicts:      kernel-default-base
# Module packages that exist for both flavors (catalog.KMP_BASES in
# nazoos-welcome); their -kmp-nazoos variants come from our kernel project
Conflicts:      nvidia-open-driver-G07-signed-kmp-default
Conflicts:      nvidia-open-driver-G06-signed-kmp-default
Conflicts:      xone-kmp-default
Conflicts:      xpadneo-kmp-default
Conflicts:      v4l2loopback-kmp-default

%description
Marker package for NazoOS: while it is installed, only the NazoOS kernel
(kernel-nazoos) is used and the openSUSE kernel (kernel-default) cannot
be installed. Remove this package to allow the openSUSE kernel again.

%prep

%build

%install
mkdir -p %{buildroot}%{_docdir}/%{name}
cat > %{buildroot}%{_docdir}/%{name}/README <<'TXT'
While this package is installed, only the NazoOS kernel is used.
Remove it (NazoOS Welcome -> Kernel -> "Use openSUSE kernel") to allow
the openSUSE kernel (kernel-default) again.
TXT

%files
%dir %{_docdir}/%{name}
%{_docdir}/%{name}/README

%changelog
