# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# The 32-bit vkBasalt layer for 32-bit Vulkan games (32-bit DXVK in
# Proton, old native games). Slowroll's vkbasalt is 64-bit only: its
# baselibs.conf only takes versioned libraries (libvkbasalt.so has no
# .so.N) and Tumbleweed builds no i586 anymore. Our repos are x86_64
# only (ADR 0016), so this is a plain -m32 cross build in the x86_64
# repo, like Arch's lib32-vkbasalt. The layer manifest names only
# "libvkbasalt.so", so the loader of a 32-bit game finds /usr/lib by
# itself and the 64-bit package's manifest serves both.
# On a version update: keep Version equal to Slowroll's vkbasalt and
# change the sha256 in _service (verify_file).

%define upname vkBasalt
Name:           vkbasalt-32bit
Version:        0.3.2.10
Release:        0
Summary:        Vulkan post processing layer (32-bit)
License:        Zlib
URL:            https://github.com/DadSchoorse/vkBasalt
Source0:        %{url}/archive/v%{version}.tar.gz#/%{upname}-%{version}.tar.gz
BuildRequires:  file
BuildRequires:  gcc-c++-32bit
BuildRequires:  glslang-devel
BuildRequires:  libX11-devel-32bit
BuildRequires:  meson
BuildRequires:  ninja
BuildRequires:  pkgconf
BuildRequires:  spirv-headers
BuildRequires:  vulkan-headers
# Layer manifest and vkBasalt.conf; same version, the layer reads the
# same config format
Requires:       vkbasalt = %{version}
ExclusiveArch:  x86_64

%description
vkBasalt is a Vulkan post processing layer to enhance the visual
graphics of games. This package contains the 32-bit layer library for
32-bit games; the configuration and the layer manifest come from the
vkbasalt package.

%prep
%autosetup -n %{upname}-%{version}
# Meson cross file: the host is 32-bit x86, pkg-config looks in /usr/lib
cat > cross32.txt <<'CROSS'
[binaries]
c = ['gcc', '-m32']
cpp = ['g++', '-m32']
pkg-config = 'pkg-config'
strip = 'strip'

[built-in options]
pkg_config_path = '/usr/lib/pkgconfig:/usr/share/pkgconfig'

[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
CROSS

%build
# Not %%meson: it sets libdir to lib64 and the 64-bit build directory
# The x86_64 optflags carry -m64, which would win over the -m32 of the
# cross file
flags="$(echo '%{optflags}' | sed 's/-m64//g')"
export CFLAGS="$flags" CXXFLAGS="$flags" LDFLAGS="$(echo '%{?build_ldflags}' | sed 's/-m64//g')"
meson setup build --cross-file cross32.txt --prefix=%{_prefix} \
  --libdir=lib --buildtype=plain -Dwith_json=false
ninja -C build %{?_smp_mflags} -v

%install
DESTDIR=%{buildroot} ninja -C build install

%check
# The point of this package: a 32-bit library
file %{buildroot}%{_prefix}/lib/libvkbasalt.so | grep -q "ELF 32-bit"

%files
%license LICENSE
%{_prefix}/lib/libvkbasalt.so

%changelog
