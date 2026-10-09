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
BuildRequires:  sysuser-tools
BuildArch:      noarch
Requires:       zram-generator
%sysusers_requires

%description
Default kernel parameters (sysctl), zram swap configuration,
udev rules (I/O schedulers, audio and SATA power management),
ntsync module loading for Wine/Proton, MGLRU working set protection,
TCP BBR, transparent huge page defrag tuning, Nvidia driver options,
a journal size limit, the i2c group for DDC/CI and RGB devices,
larger shader caches, GameMode defaults, a lower PipeWire default
latency and the SDDM greeter on Wayland, tuned for gaming and desktop
responsiveness on NazoOS.

%prep
%autosetup

%build
# Nothing to compile; generate the pre-install script that creates the i2c group
%sysusers_generate_pre sysusers.d/nazoos-i2c.conf nazoos-i2c nazoos-i2c.conf

%install
install -Dm0644 sysctl.d/70-nazoos.conf %{buildroot}%{_sysctldir}/70-nazoos.conf
install -Dm0644 zram-generator.conf.d/70-nazoos.conf \
  %{buildroot}%{_prefix}/lib/systemd/zram-generator.conf.d/70-nazoos.conf
install -Dm0644 tmpfiles.d/70-nazoos.conf %{buildroot}%{_tmpfilesdir}/nazoos-tweaks.conf
install -Dm0644 -t %{buildroot}%{_udevrulesdir} udev/*.rules
install -Dm0644 modules-load.d/ntsync.conf %{buildroot}%{_modulesloaddir}/nazoos-ntsync.conf
install -Dm0644 modules-load.d/bbr.conf %{buildroot}%{_modulesloaddir}/nazoos-bbr.conf
install -Dm0644 modprobe.d/nvidia.conf %{buildroot}%{_modprobedir}/70-nazoos-nvidia.conf
install -Dm0644 journald.conf.d/70-nazoos.conf \
  %{buildroot}%{_prefix}/lib/systemd/journald.conf.d/70-nazoos.conf
install -Dm0644 -t %{buildroot}%{_datadir}/pipewire/pipewire.conf.d \
  pipewire/pipewire.conf.d/10-nazoos-latency.conf
install -Dm0644 -t %{buildroot}%{_unitdir}/display-manager-legacy.service.d \
  systemd/display-manager-legacy.service.d/10-nazoos-tty1.conf
install -Dm0644 systemd/90-nazoos.preset %{buildroot}%{_presetdir}/90-nazoos.preset
install -Dm0644 -t %{buildroot}%{_prefix}/lib/sddm/sddm.conf.d \
  sddm/10-nazoos-wayland.conf
install -Dm0644 -t %{buildroot}%{_prefix}/lib/environment.d \
  environment.d/70-nazoos-shader-cache.conf
install -Dm0644 sysusers.d/nazoos-i2c.conf %{buildroot}%{_sysusersdir}/nazoos-i2c.conf
install -Dm0644 gamemode/gamemode.ini %{buildroot}%{_sysconfdir}/gamemode.ini

%pre -f nazoos-i2c.pre

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
%dir %{_modulesloaddir}
%{_modulesloaddir}/nazoos-ntsync.conf
%{_modulesloaddir}/nazoos-bbr.conf
%dir %{_modprobedir}
%{_modprobedir}/70-nazoos-nvidia.conf
%dir %{_prefix}/lib/systemd/journald.conf.d
%{_prefix}/lib/systemd/journald.conf.d/70-nazoos.conf
%dir %{_datadir}/pipewire
%dir %{_datadir}/pipewire/pipewire.conf.d
%{_datadir}/pipewire/pipewire.conf.d/10-nazoos-latency.conf
%dir %{_unitdir}/display-manager-legacy.service.d
%{_unitdir}/display-manager-legacy.service.d/10-nazoos-tty1.conf
%{_presetdir}/90-nazoos.preset
%dir %{_prefix}/lib/sddm
%dir %{_prefix}/lib/sddm/sddm.conf.d
%{_prefix}/lib/sddm/sddm.conf.d/10-nazoos-wayland.conf
%dir %{_prefix}/lib/environment.d
%{_prefix}/lib/environment.d/70-nazoos-shader-cache.conf
%{_sysusersdir}/nazoos-i2c.conf
%config(noreplace) %{_sysconfdir}/gamemode.ini

%changelog
