# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is not in Tumbleweed
# (TODO.md "Controllers / input" in NazoOS-dev). The source tarball is
# downloaded by the OBS service download_files from the Source0 URL.
# Lives next to steam-devices: different file names (71-*-gdu.rules vs.
# 60-steam-*.rules), overlapping rules only add the same uaccess tag.

Name:           game-devices-udev
Version:        1.1
Release:        0
Summary:        Udev rules for game controllers, wheels and flight sticks
License:        MIT
URL:            https://codeberg.org/fabiscafe/game-devices-udev
# Codeberg names the archive after the tag only; "#/" renames the download
Source0:        %{url}/archive/%{version}.tar.gz#/%{name}-%{version}.tar.gz
BuildRequires:  meson
BuildRequires:  pkgconfig(udev)
BuildArch:      noarch

%description
Udev rules that give the logged-in user access to game controllers,
racing wheels, flight sticks and VR devices from 8BitDo, Hori, Logitech,
Microsoft, Nintendo, PowerA, Razer, Sony, Thrustmaster, Valve and more
(hidraw and USB nodes, for Steam Input and configuration tools), and
create /dev/uinput with user access for virtual controllers.

%prep
%autosetup -n %{name}

%build
%meson -Dudev_priority=71
%meson_build

%install
%meson_install

%post
%udev_rules_update

%postun
%udev_rules_update

%files
%license LICENSE
%doc README.md NEWS.md
%{_udevrulesdir}/71-*.rules

%changelog
