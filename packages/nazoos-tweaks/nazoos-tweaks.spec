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
# sysctl in nazoos-tcp-bbr(3).service
Requires:       procps
Requires:       zram-generator
%sysusers_requires
%{?systemd_ordering}
# One line: the %service_* macros do not take line continuations
%define units nazoos-xone-firmware.service nazoos-xone-firmware.timer nazoos-tcp-bbr.service nazoos-tcp-bbr3.service

%description
Default kernel parameters (sysctl), zram swap configuration,
udev rules (I/O schedulers, audio and SATA power management),
ntsync module loading for Wine/Proton, MGLRU working set protection,
TCP BBR, transparent huge page defrag tuning, Nvidia driver options,
a journal size limit, the i2c group for DDC/CI and RGB devices,
larger shader caches, GameMode defaults, a lower PipeWire default
latency, the SDDM greeter on Wayland, the NazoOS firewall zone and the
signing key of the NazoOS package repository, a polkit rule that lets
fwupd-refresh.service load firmware metadata and a timer that downloads
the Xbox wireless dongle firmware once the system is online, tuned for gaming and desktop
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
install -Dm0644 modprobe.d/nvidia.conf %{buildroot}%{_modprobedir}/70-nazoos-nvidia.conf
install -Dm0644 journald.conf.d/70-nazoos.conf \
  %{buildroot}%{_prefix}/lib/systemd/journald.conf.d/70-nazoos.conf
install -Dm0644 -t %{buildroot}%{_datadir}/pipewire/pipewire.conf.d \
  pipewire/pipewire.conf.d/10-nazoos-latency.conf
install -Dm0644 -t %{buildroot}%{_unitdir}/display-manager-legacy.service.d \
  systemd/display-manager-legacy.service.d/10-nazoos-tty1.conf
install -Dm0644 systemd/90-nazoos.preset %{buildroot}%{_presetdir}/90-nazoos.preset
install -Dm0644 -t %{buildroot}%{_unitdir} \
  systemd/nazoos-xone-firmware.service systemd/nazoos-xone-firmware.timer \
  systemd/nazoos-tcp-bbr.service systemd/nazoos-tcp-bbr3.service
install -Dm0644 -t %{buildroot}%{_prefix}/lib/sddm/sddm.conf.d \
  sddm/10-nazoos-wayland.conf
install -Dm0644 -t %{buildroot}%{_prefix}/lib/environment.d \
  environment.d/70-nazoos-shader-cache.conf
install -Dm0644 sysusers.d/nazoos-i2c.conf %{buildroot}%{_sysusersdir}/nazoos-i2c.conf
# Firewall zone, made the default zone by kiwi config.sh (ADR 0021), and the
# zone + policy of Waydroid's bridge
install -Dm0644 -t %{buildroot}%{_prefix}/lib/firewalld/zones \
  firewalld/nazoos.xml firewalld/nazoos-waydroid.xml
install -Dm0644 -t %{buildroot}%{_prefix}/lib/firewalld/policies \
  firewalld/policies/nazoos-waydroid-out.xml
# Before openSUSE's 90-default-privs.rules, which would deny fwupd-refresh
install -Dm0644 -t %{buildroot}%{_datadir}/polkit-1/rules.d \
  polkit/49-nazoos-fwupd-refresh.rules
install -Dm0644 gamemode/gamemode.ini %{buildroot}%{_sysconfdir}/gamemode.ini
# Signing key of the OBS projects home:Tokajer:nazoos:* (osc signkey
# home:Tokajer). Same place as openSUSE-build-key; the image imports all
# keys from there (kiwi config.sh)
install -Dm0644 -t %{buildroot}%{_prefix}/lib/rpm/gnupg/keys rpm-keys/*.asc

%pre -f nazoos-i2c.pre
# Upgrade from the version with modules-load.d/nazoos-bbr.conf: its copy in
# the initrd loads tcp_bbr, which blocks bbr3 → rebuild the initrd once
if [ -e %{_modulesloaddir}/nazoos-bbr.conf ]; then
  mkdir -p /run/nazoos-tweaks && touch /run/nazoos-tweaks/regenerate-initrd
fi
%service_add_pre %{units}

%post
%sysctl_apply 70-nazoos.conf
%tmpfiles_create nazoos-tweaks.conf
%udev_rules_update
if [ -e /run/nazoos-tweaks/regenerate-initrd ]; then
  rm -f /run/nazoos-tweaks/regenerate-initrd
  %regenerate_initrd_post
fi
%service_add_post %{units}
# A running firewalld only reads new zone/policy files after a reload; only
# then, since a reload drops runtime-only rules
if %{_bindir}/firewall-cmd --state >/dev/null 2>&1 &&
   ! %{_bindir}/firewall-cmd --get-zones | grep -qw nazoos-waydroid; then
  %{_bindir}/firewall-cmd --reload --quiet >/dev/null 2>&1 || :
fi

%preun
%service_del_preun %{units}

%posttrans
%regenerate_initrd_posttrans

%postun
%service_del_postun %{units}

%files
%{_sysctldir}/70-nazoos.conf
%dir %{_prefix}/lib/systemd/zram-generator.conf.d
%{_prefix}/lib/systemd/zram-generator.conf.d/70-nazoos.conf
%{_tmpfilesdir}/nazoos-tweaks.conf
%{_udevrulesdir}/*-nazoos-*.rules
%dir %{_modulesloaddir}
%{_modulesloaddir}/nazoos-ntsync.conf
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
%{_unitdir}/nazoos-xone-firmware.service
%{_unitdir}/nazoos-xone-firmware.timer
%{_unitdir}/nazoos-tcp-bbr.service
%{_unitdir}/nazoos-tcp-bbr3.service
%dir %{_prefix}/lib/sddm
%dir %{_prefix}/lib/sddm/sddm.conf.d
%{_prefix}/lib/sddm/sddm.conf.d/10-nazoos-wayland.conf
%dir %{_prefix}/lib/environment.d
%{_prefix}/lib/environment.d/70-nazoos-shader-cache.conf
%{_sysusersdir}/nazoos-i2c.conf
%dir %{_prefix}/lib/firewalld
%dir %{_prefix}/lib/firewalld/zones
%{_prefix}/lib/firewalld/zones/nazoos.xml
%{_prefix}/lib/firewalld/zones/nazoos-waydroid.xml
%dir %{_prefix}/lib/firewalld/policies
%{_prefix}/lib/firewalld/policies/nazoos-waydroid-out.xml
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/rules.d
%{_datadir}/polkit-1/rules.d/49-nazoos-fwupd-refresh.rules
%config(noreplace) %{_sysconfdir}/gamemode.ini
%dir %{_prefix}/lib/rpm/gnupg
%dir %{_prefix}/lib/rpm/gnupg/keys
%{_prefix}/lib/rpm/gnupg/keys/gpg-pubkey-a686e7d6-6ac40415.asc

%changelog
