# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Waydroid requires "(binder-dkms or binder-kmp)". kernel-nazoos has Binder
# built in (kernel/config/nazoos.fragment), so no module package is needed:
# this marker satisfies the requirement instead of pulling kernel-default
# (binder-kmp-default) or a compiler (binder-dkms). Installed with Waydroid
# by nazoos-welcome; removed with it when kernel-nazoos goes away.

Name:           nazoos-binder
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Binder for Waydroid, built into the NazoOS kernel
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
BuildArch:      noarch
Requires:       kernel-nazoos
Provides:       binder-kmp = %{version}
# A binder_linux module would clash with the built-in Binder (binderfs is
# registered twice, systemd-modules-load fails at boot)
Conflicts:      binder-kmp-default
Conflicts:      binder-dkms

%description
Marker package for NazoOS: the NazoOS kernel (kernel-nazoos) has the
Binder driver for Waydroid built in. This package tells the package
manager so, instead of installing a separate Binder module.

%prep

%build

%install
mkdir -p %{buildroot}%{_docdir}/%{name}
cat > %{buildroot}%{_docdir}/%{name}/README <<'TXT'
Binder (needed by Waydroid) is built into the NazoOS kernel.
With the openSUSE kernel (kernel-default) Waydroid does not work.
TXT

%files
%dir %{_docdir}/%{name}
%{_docdir}/%{name}/README

%changelog
