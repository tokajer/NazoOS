# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream kernel module, packaged for NazoOS because it is not in
# Tumbleweed. Built in home:Tokajer:nazoos:kernel only: kernel-syms there
# has the nazoos flavor, so this gives acpi_call-kmp-nazoos, signed with
# the project key like the kernel. No -kmp-default (Secure Boot would need
# our key on the openSUSE kernel too); nazoos-welcome installs it together
# with kernel-nazoos (nazoos_common.kernel.KMP_NAZOOS_ONLY).
# Upstream has no release since 1.2.2 (2021); pinned to a master commit
# with fixes for newer kernels. On an update: change commit and Version.
#
# needssslcertforbuild

%global commit 6ad1e676dbfb5dcb1ec1f973c10ef5c57ffb4069

Name:           acpi_call
Version:        1.2.2+git20260811.6ad1e67
Release:        0
Summary:        Kernel module to call ACPI methods from user space
License:        GPL-3.0-or-later
URL:            https://github.com/nix-community/acpi_call
Source0:        %{url}/archive/%{commit}/%{name}-%{commit}.tar.gz
Source1:        preamble
BuildRequires:  %{kernel_module_package_buildreqs}
BuildRequires:  pesign-obs-integration
%kernel_module_package -n %{name} -x debug -x trace -c %{_sourcedir}/_projectcert.crt -p %{_sourcedir}/preamble

%description
acpi_call exposes /proc/acpi/call, through which root can call ACPI
methods of the firmware. Handheld tools (Handheld Daemon, SimpleDeckyTDP)
use it to set the power limit (TDP) and fan modes on devices such as the
Lenovo Legion Go, where no kernel driver offers these settings yet.

%prep
%autosetup -n %{name}-%{commit}
set -- *
mkdir source
mv "$@" source/
mkdir obj

%build
for flavor in %{flavors_to_build}; do
    rm -rf obj/$flavor
    cp -r source obj/$flavor
    make -C %{kernel_source $flavor} modules M=$PWD/obj/$flavor
done

%install
export INSTALL_MOD_PATH=%{buildroot}
export INSTALL_MOD_DIR=updates
for flavor in %{flavors_to_build}; do
    make -C %{kernel_source $flavor} modules_install M=$PWD/obj/$flavor
done
# Sign the module with the project key (pesign-obs-integration)
export BRP_PESIGN_FILES='*.ko'

%changelog
