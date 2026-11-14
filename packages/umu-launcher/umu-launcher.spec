# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is not in Tumbleweed or
# Slowroll. umu runs non-Steam games with Proton inside the Steam Linux
# Runtime; Lutris and Heroic use it, Nobara ships it. Built with the system
# urllib3 and pyzstd (both in repo-oss), so nothing is bundled but the Rust
# crates of the small umu_delta module (delta updates of Proton), which
# come from vendor.tar.zst (cargo_vendor, mode manual, see _service).
# On a version update: change Version, the sha256 in _service and the src
# parameter of cargo_vendor, then make a new vendor.tar.zst.

Name:           umu-launcher
Version:        1.4.4
Release:        0
Summary:        Unified launcher for Windows games on Linux with Proton
License:        GPL-3.0-only
URL:            https://github.com/Open-Wine-Components/umu-launcher
Source0:        %{url}/archive/%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        vendor.tar.zst
BuildRequires:  cargo-packaging
BuildRequires:  python3-build
BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-installer
BuildRequires:  python3-wheel
BuildRequires:  scdoc
BuildRequires:  zstd
Requires:       python3-python-xlib >= 0.33
Requires:       python3-urllib3 >= 2.0.0
# Use the system's CA store instead of certifi's
Requires:       python3-truststore
# Delta updates of Proton and the runtime (otherwise full downloads)
Recommends:     python3-cbor2
Recommends:     python3-pyzstd
Recommends:     python3-xxhash
ExclusiveArch:  %{rust_tier1_arches}

%description
umu-launcher runs Windows games with Proton outside of Steam, inside the
Steam Linux Runtime, the same way Steam does. Game launchers such as
Lutris and Heroic use it, and it applies the protonfixes of the game.

%prep
%autosetup -a1

%build
./configure.sh --prefix=%{_prefix} --use-system-pyzstd --use-system-urllib
# The Makefile calls cargo itself; vendor.tar.zst brought .cargo/config.toml
# pointing at the vendored crates, and OBS has no network
export CARGO_NET_OFFLINE=true
%make_build

%install
%make_install PYTHONDIR=%{python3_sitelib}
# The wheel's entry point is written with the build python; pin it to the
# python3 whose site-packages hold umu
sed -i '1s|^#!.*python.*$|#!%{_bindir}/python%{python3_bin_suffix}|' \
  %{buildroot}%{_bindir}/umu-run
# Only filled when urllib3/pyzstd are bundled, which we do not
rmdir %{buildroot}%{python3_sitelib}/umu/_vendor

%check
# Imports and the compiled module load with the system packages
# (-P: not the source tree's umu/, which lacks the compiled module)
export PYTHONPATH=%{buildroot}%{python3_sitelib}
python3 -P -c "import umu.umu_run, umu.umu_delta"
%{buildroot}%{_bindir}/umu-run --version

%files
%license LICENSE
%doc README.md
%{_bindir}/umu-run
%{python3_sitelib}/umu
%{python3_sitelib}/umu_launcher-%{version}.dist-info
%{_mandir}/man1/umu.1%{?ext_man}
%{_mandir}/man5/umu.5%{?ext_man}

%changelog
