# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Upstream software, packaged for NazoOS because it is neither in
# Tumbleweed nor on Flathub. Opt-in in NazoOS Welcome, not in the pattern
# (ADR 0033). Source0 is downloaded by the OBS service download_files,
# vendor.tar.zst made by cargo_vendor.
# On a version update: change Version and the src parameter in _service.

Name:           artcraft-launcher
Version:        0.11.1
# On a version update also change the sha256 in _service (verify_file)
Release:        0
Summary:        Installs, updates and opens the Craft App Suite
License:        Apache-2.0 OR MIT
URL:            https://github.com/storytold/craft-launcher
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        vendor.tar.zst
# Upstream's self-update would replace this signed RPM with its unsigned
# one. Updates of the launcher come from our repo like everything else
Patch0:         no-self-update.patch
BuildRequires:  cargo-packaging
BuildRequires:  desktop-file-utils
BuildRequires:  hicolor-icon-theme
BuildRequires:  zstd
# Loaded with dlopen at run time, so rpm finds no dependency on them (list
# from upstream's packaging/linux/nfpm.yaml)
Requires:       libX11-6
Requires:       libX11-xcb1
Requires:       libXcursor1
Requires:       libXi6
Requires:       libvulkan1
Requires:       libwayland-client0
Requires:       libxcb1
Requires:       libxkbcommon-x11-0
Requires:       libxkbcommon0
Requires:       hicolor-icon-theme
Recommends:     xdg-desktop-portal
ExclusiveArch:  %{rust_tier1_arches}

%description
ArtCraft Launcher lists the apps of the Craft App Suite (PhotoCraft,
VectorCraft, FilmCraft, PdfCraft, WordCraft, GridCraft and others),
installs them from their GitHub releases and tells you about updates.
The launcher itself updates through the system updates.

%prep
%autosetup -a1 -p1 -n craft-launcher-%{version}
# Unused entries of [patch.crates-io] ([[patch.unused]] in Cargo.lock):
# cargo vendor leaves these crates out and the offline build stops there
sed -i -E '/^(egui_demo_lib|egui_inspection|egui_system_font_provider) = /d' Cargo.toml

%build
%{cargo_build} -p artcraft-launcher

%install
install -Dm0755 target/release/%{name} %{buildroot}%{_bindir}/%{name}
install -Dm0644 packaging/linux/ai.storyteller.%{name}.desktop \
  %{buildroot}%{_datadir}/applications/ai.storyteller.%{name}.desktop
mkdir -p %{buildroot}%{_datadir}/icons
cp -R assets/app-icon/hicolor %{buildroot}%{_datadir}/icons/
%check
desktop-file-validate %{buildroot}%{_datadir}/applications/ai.storyteller.%{name}.desktop

%files
%license LICENSE-APACHE LICENSE-MIT NOTICE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/applications/ai.storyteller.%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/*

%changelog
