# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-common
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Code shared by the NazoOS apps
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  python3
BuildArch:      noarch
Requires:       python3
# Raised when the apps need new modules (2: proc, kernel;
# 3: repos, write_atomic, app bootstrap; 4: grub.py, launchers per app;
# 5: zypper.py, kernel.stable/kmp, helper.reboot, LogDialog;
# 6: launcher.py, shellconf.py, kernel.wanted_kmps, CoalescedLoad;
# 7: kmp_sync.py, kernel.stage2_state/stage2_now/stage2_due)
Provides:       nazoos-common(api) = 7
# nazoos_common.qt only; the root helpers use the other modules
Recommends:     python3-pyside6

%description
Python modules shared by NazoOS Welcome and NazoOS Update: the frame of
their root helpers (started via pkexec) and its error messages, the
Secure Boot key check and the NazoOS kernel opt-in, and the Qt side that
runs the helpers. Also a shared QML log view.

%prep
%autosetup

%build

%install
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-common/nazoos_common \
  nazoos_common/*.py
# Byte-compile at build time: users cannot write __pycache__ below /usr
python3 -m compileall -q --invalidation-mode checked-hash \
  -d %{_datadir}/nazoos-common/nazoos_common \
  %{buildroot}%{_datadir}/nazoos-common/nazoos_common
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-common/qml/org/nazoos/common \
  qml/org/nazoos/common/*

%check
# Everything but the Qt part imports without PySide6
PYTHONPATH=. python3 -B -c "import nazoos_common.errors, nazoos_common.grub, nazoos_common.helper, nazoos_common.i18n, nazoos_common.kernel, nazoos_common.kernelstate, nazoos_common.kmp_sync, nazoos_common.launcher, nazoos_common.mok, nazoos_common.proc, nazoos_common.repos, nazoos_common.shellconf, nazoos_common.zypper"

%files
%{_datadir}/nazoos-common

%changelog
