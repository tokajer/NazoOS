# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-pattern
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        NazoOS Gaming Desktop
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
BuildArch:      noarch
# Pattern metadata, read by zypper, YaST and KIWI
Provides:       pattern() = nazoos
Provides:       pattern-category() = NazoOS
Provides:       pattern-icon() = pattern-games
Provides:       pattern-order() = 1000
Provides:       pattern-visible()
# Core: removing it would remove the pattern
Requires:       nazoos-tweaks
Requires:       nazoos-branding
# Existing installs get the repo definitions with their next update; without
# them an install cannot be moved to :release
Requires:       nazoos-repos
# Fallback: older Calamares configs wrote classic console keymap names;
# Tumbleweed's kbd only ships XKB-generated ones, the rest is in kbd-legacy
Requires:       kbd-legacy
# setfacl: udev rules (e.g. ddcutil i2c) grant device access via ACLs
Requires:       acl
# sudo and polkit dialogs ask members of wheel for their own password
# instead of root's; root stays locked on new installs (ADR 0032)
Requires:       sudo-policy-wheel-auth-self
# Apps and extras: installed by default, but users may remove them
# Gaming
Recommends:     steam
Recommends:     steam-devices
# More controllers, wheels and flight sticks than steam-devices (own OBS
# package from codeberg.org/fabiscafe/game-devices-udev)
Recommends:     game-devices-udev
Recommends:     lutris
Recommends:     gamemode
Recommends:     mangohud
Recommends:     gamescope
# Steam's gaming mode (Steam Deck interface) as a login session, with a
# "Gaming Mode" switch in the menu and Steam's "Switch to Desktop"
Recommends:     nazoos-session
Recommends:     wine
Recommends:     protontricks
Recommends:     winetricks
Recommends:     goverlay
# Voice chat (non-oss like steam)
Recommends:     discord
# Both CPU vendors, the image is built without knowing the hardware. The
# patterns we install do not pull microcode, and without it the CPU runs
# whatever the BIOS shipped
Recommends:     ucode-intel
Recommends:     ucode-amd
# Without it cfg80211 stays on the world regulatory domain
Recommends:     wireless-regdb
# Graphics: all Mesa drivers regardless of hardware. Tumbleweed only pulls
# the Vulkan drivers via modalias supplements, which do not match in an
# image built without a GPU (KIWI/OBS) and are bound to kernel-default.
# 32-bit variants for 32-bit games under Proton/Wine and the Steam client
Recommends:     Mesa-dri
Recommends:     Mesa-dri-32bit
Recommends:     Mesa-libGL1-32bit
Recommends:     Mesa-libva
# VA-API on Intel: Mesa-libva only covers AMD and Nouveau
Recommends:     intel-media-driver
Recommends:     Mesa-vulkan-device-select
Recommends:     Mesa-vulkan-device-select-32bit
Recommends:     libvulkan_radeon
Recommends:     libvulkan_radeon-32bit
Recommends:     libvulkan_intel
Recommends:     libvulkan_intel-32bit
# NVK: Vulkan on NVIDIA before the proprietary driver is installed
Recommends:     libvulkan_nouveau
Recommends:     libvulkan_nouveau-32bit
# vulkaninfo for bug reports and the llvmpipe check
Recommends:     vulkan-tools
# Xbox controllers: wireless dongle (xone) and Bluetooth (xpadneo). The
# base packages require the generic xone-kmp/xpadneo-kmp, provided by
# -kmp-default and -kmp-nazoos alike (ADR 0008 stage 2 keeps working)
Recommends:     xone
Recommends:     xpadneo
# Nintendo Switch: pairs two Joy-Cons into one controller (service
# enabled by the nazoos-tweaks preset; joycond-autoload comes with it)
Recommends:     joycond
# Hardware
Recommends:     OpenRGB
Recommends:     lact
Recommends:     coolercontrol
Recommends:     fwupd
Recommends:     power-profiles-daemon
# VRAM for the focused game (dmem cgroup, ADR 0013): full effect with
# kernel-nazoos, plain dmem protection with kernel-default
Recommends:     dmemcg-booster
Recommends:     plasma-foreground-booster
# Scheduler, toggled by nazoos-welcome (ADR 0002)
Recommends:     scx
# Audio
Recommends:     pipewire-config-upmix
Recommends:     rtkit
# First steps after installation (drivers, codecs, apps)
Recommends:     nazoos-welcome
# Updates with notifications, rollback after booting a snapshot
Recommends:     nazoos-update
Recommends:     btrfs-assistant
# System settings that YaST used to cover (YaST is not in the image):
# firewall page in System Settings, partitioning
Recommends:     plasma6-firewall
Recommends:     partitionmanager
# Software management
Recommends:     discover6
Recommends:     discover6-backend-flatpak
Recommends:     flatpak
Recommends:     flatpak-remote-flathub
Recommends:     myrlyn
# AppImages: older ones (AppImageKit runtime, libfuse2) call fusermount
# from fuse 2 and fail with "AppImages require FUSE to run" without it;
# the newer static runtime uses fusermount3 (fuse3, already in the base)
Recommends:     fuse
Recommends:     libfuse2
# Desktop
Recommends:     MozillaFirefox
Recommends:     kate
Recommends:     ark
Recommends:     okular
Recommends:     gwenview
Recommends:     kcalc
Recommends:     filelight
Recommends:     spectacle
Recommends:     kdeconnect-kde
Recommends:     elisa
# Video player (mpv); full codecs after the Packman opt-in
Recommends:     haruna
# Video and PDF previews in Dolphin
Recommends:     ffmpegthumbs
Recommends:     kdegraphics-thumbnailers
Recommends:     kamoso
Recommends:     kfind
Recommends:     kcharselect
# Encrypted folders (gocryptfs backend comes as its Recommends)
Recommends:     plasma6-vault
# System logs in a window instead of journalctl
Recommends:     kjournald
# Edit system files in Dolphin (admin://) instead of a root terminal
Recommends:     kio-admin
Recommends:     pavucontrol-qt
# Fingerprint login on laptops (no effect without a sensor)
Recommends:     fprintd
Recommends:     fprintd-pam
# Drivers for many Epson and Canon printers (HP: HPLIP in nazoos-welcome)
Recommends:     gutenprint
# Remote desktop page in System Settings
Recommends:     krdp6
# Audio CDs in Dolphin
Recommends:     kio_audiocd
# Monitor colour profiles in System Settings
Recommends:     colord-kde
# CJK glyphs in game titles and launchers
Recommends:     google-noto-sans-cjk-fonts
Recommends:     noto-coloremoji-fonts
Recommends:     alsa-firmware
# USB sticks, SD cards and Windows disks (dual boot)
Recommends:     exfatprogs
Recommends:     ntfs-3g
# Command line basics (like CachyOS/Nobara); patterns-base-base is
# minimal and ships no editor
Recommends:     nano
Recommends:     vim
Recommends:     bash-completion
Recommends:     fastfetch
Recommends:     btop
# GPU load, VRAM and temperature (btop barely shows the GPU)
Recommends:     nvtop
Recommends:     git-core
Recommends:     wget
Recommends:     unzip
# .7z archives in Ark
Recommends:     7zip
Recommends:     plocate
Recommends:     ethtool
Recommends:     openssh-clients
# Asked for in nearly every support thread, not in patterns-base-base
Recommends:     man
Recommends:     man-pages
Recommends:     usbutils
Recommends:     lsof
Recommends:     zip
Recommends:     bc
Recommends:     whois
Recommends:     traceroute
# Debugging RGB and DDC/CI devices (group i2c: nazoos-tweaks)
Recommends:     i2c-tools
# Real size of compressed btrfs files
Recommends:     compsize
# Konsole profile and prompt from nazoos-branding
Recommends:     starship
Recommends:     ibm-plex-mono-fonts
Recommends:     nerdfonts-symbolsonly-fonts
# Translations of the desktop (subpackage below)
Recommends:     nazoos-translations

%description
Installs the NazoOS gaming desktop: system tweaks, Steam, Lutris,
Wine, Gamescope with Steam's gaming mode, MangoHud, GameMode, hardware
tools, graphical software management (Discover with Flatpak, Myrlyn),
updates with notifications (nazoos-update) and snapshots (Btrfs
Assistant).

%package -n nazoos-translations
Summary:        Translations for the NazoOS desktop
# Tumbleweed splits translations into <package>-lang subpackages (all
# languages in one package). zypper adds them only for the languages in
# /var/lib/zypp/RequestedLocales, and KIWI builds the image with "en"
# only, so a German install showed Plasma, SDDM and polkit dialogs in
# English (ADR 0027). Weak dependencies on purpose: a package that is
# renamed or dropped in Tumbleweed must not block "zypper dup".
# List = every <name>-lang whose <name> is in the image; refresh it with
# notes/translations.md (2026-10-25: 209 packages).
Recommends:     accountsservice-lang
Recommends:     appstream-glib-lang
Recommends:     AppStream-lang
Recommends:     ark-lang
Recommends:     at-spi2-core-lang
Recommends:     aurorae6-lang
Recommends:     avahi-lang
Recommends:     baloo-widgets-lang
Recommends:     bash-lang
Recommends:     bluedevil6-lang
Recommends:     breeze6-style-lang
Recommends:     colord-kde-lang
Recommends:     coreutils-lang
Recommends:     cpio-lang
Recommends:     cryptsetup-lang
Recommends:     cups-pk-helper-lang
Recommends:     dialog-lang
Recommends:     diffutils-lang
Recommends:     discover6-lang
Recommends:     dolphin-part-lang
Recommends:     drkonqi6-lang
Recommends:     elfutils-lang
Recommends:     elisa-lang
Recommends:     filelight-lang
Recommends:     findutils-lang
Recommends:     firewalld-lang
Recommends:     flatpak-kcm6-lang
Recommends:     fontconfig-lang
Recommends:     fprintd-lang
Recommends:     fwupd-lang
Recommends:     gcab-lang
Recommends:     glib-networking-lang
Recommends:     glibc-lang
Recommends:     gpg2-lang
Recommends:     grep-lang
Recommends:     gsettings-desktop-schemas-lang
Recommends:     gstreamer-lang
Recommends:     gstreamer-plugins-bad-lang
Recommends:     gstreamer-plugins-base-lang
Recommends:     gstreamer-plugins-good-lang
Recommends:     gvfs-lang
Recommends:     gwenview-lang
Recommends:     haruna-lang
Recommends:     kaccounts-integration-lang
Recommends:     kaccounts-providers-lang
Recommends:     kactivitymanagerd6-lang
Recommends:     kamoso-lang
Recommends:     kate-lang
Recommends:     kcalc-lang
Recommends:     kcharselect-lang
Recommends:     kcoreaddons-lang
Recommends:     kde-cli-tools6-lang
Recommends:     kdeconnect-kde-lang
Recommends:     kded-lang
Recommends:     kdenetwork-filesharing-lang
Recommends:     kdeplasma6-addons-lang
Recommends:     kdialog-lang
Recommends:     kdoctools-lang
Recommends:     kf6-kauth-lang
Recommends:     kf6-kcmutils-lang
Recommends:     kf6-kcoreaddons-lang
Recommends:     kf6-kded-lang
Recommends:     kf6-kdoctools-lang
Recommends:     kf6-kfilemetadata-lang
Recommends:     kf6-kio-lang
Recommends:     kf6-kpackage-lang
Recommends:     kf6-kservice-lang
Recommends:     kf6-ktexteditor-lang
Recommends:     kf6-kuserfeedback-lang
Recommends:     kf6-kwallet-tools-lang
Recommends:     kf6-purpose-lang
Recommends:     kf6-qqc2-desktop-style-lang
Recommends:     kfind-lang
Recommends:     kgamma6-lang
Recommends:     khelpcenter-lang
Recommends:     kinfocenter6-lang
Recommends:     kinit-lang
Recommends:     kio-admin-lang
Recommends:     kio-extras-lang
Recommends:     kio-lang
Recommends:     kio_audiocd-lang
Recommends:     kirigami-addons6-lang
Recommends:     kirigami2-lang
Recommends:     kjournald-lang
Recommends:     kmenuedit6-lang
Recommends:     konsole-part-lang
Recommends:     kpmcore-lang
Recommends:     krdp6-lang
Recommends:     kscreen6-lang
Recommends:     kscreenlocker6-lang
Recommends:     kservice-lang
Recommends:     ksystemstats6-lang
Recommends:     kuiviewer-lang
Recommends:     kwalletd6-lang
Recommends:     kwalletmanager-lang
Recommends:     kwin6-lang
Recommends:     libgphoto2-6-lang
Recommends:     libkdecorations3-6-lang
Recommends:     libKF5Archive5-lang
Recommends:     libKF5Auth5-lang
Recommends:     libKF5Bookmarks5-lang
Recommends:     libKF5Codecs5-lang
Recommends:     libKF5Completion5-lang
Recommends:     libKF5ConfigCore5-lang
Recommends:     libKF5ConfigWidgets5-lang
Recommends:     libKF5DBusAddons5-lang
Recommends:     libKF5GlobalAccel5-lang
Recommends:     libKF5I18n5-lang
Recommends:     libKF5IconThemes5-lang
Recommends:     libKF5ItemViews5-lang
Recommends:     libKF5JobWidgets5-lang
Recommends:     libKF5Notifications5-lang
Recommends:     libKF5Solid5-lang
Recommends:     libKF5SonnetCore5-lang
Recommends:     libKF5TextWidgets5-lang
Recommends:     libKF5WidgetsAddons5-lang
Recommends:     libKF5WindowSystem5-lang
Recommends:     libKF5XmlGui5-lang
Recommends:     libKF6Archive6-lang
Recommends:     libKF6Baloo6-lang
Recommends:     libKF6Bookmarks6-lang
Recommends:     libKF6CalendarEvents6-lang
Recommends:     libKF6Codecs6-lang
Recommends:     libKF6ColorScheme6-lang
Recommends:     libKF6Completion6-lang
Recommends:     libKF6ConfigCore6-lang
Recommends:     libKF6ConfigWidgets6-lang
Recommends:     libKF6Contacts6-lang
Recommends:     libKF6DBusAddons6-lang
Recommends:     libKF6DNSSD6-lang
Recommends:     libKF6GlobalAccel6-lang
Recommends:     libKF6Holidays6-lang
Recommends:     libKF6I18n6-lang
Recommends:     libKF6IconThemes6-lang
Recommends:     libKF6ItemViews6-lang
Recommends:     libKF6JobWidgets6-lang
Recommends:     libKF6KCMUtils6-lang
Recommends:     libKF6NewStuffCore6-lang
Recommends:     libKF6NotifyConfig6-lang
Recommends:     libKF6Parts6-lang
Recommends:     libKF6Pty6-lang
Recommends:     libKF6Screen8-lang
Recommends:     libKF6Solid6-lang
Recommends:     libKF6SonnetCore6-lang
Recommends:     libKF6StatusNotifierItem6-lang
Recommends:     libKF6Su6-lang
Recommends:     libKF6SyntaxHighlighting6-lang
Recommends:     libKF6TextWidgets6-lang
Recommends:     libKF6UnitConversion6-lang
Recommends:     libKF6WidgetsAddons6-lang
Recommends:     libKF6WindowSystem6-lang
Recommends:     libKF6XmlGui6-lang
Recommends:     libKPipeWire6-lang
Recommends:     libksysguard6-lang
Recommends:     libPlasma5Support6-lang
Recommends:     lutris-lang
Recommends:     maliit-keyboard-lang
Recommends:     markdownpart-lang
Recommends:     milou6-lang
Recommends:     ModemManager-lang
Recommends:     MozillaFirefox-translations-common
Recommends:     nano-lang
Recommends:     NetworkManager-lang
Recommends:     notification-daemon-lang
Recommends:     okular-lang
Recommends:     PackageKit-lang
Recommends:     parted-lang
Recommends:     partitionmanager-lang
Recommends:     pavucontrol-qt-lang
Recommends:     pipewire-lang
Recommends:     plasma6-browser-integration-lang
Recommends:     plasma6-desktop-lang
Recommends:     plasma6-disks-lang
Recommends:     plasma6-firewall-lang
Recommends:     plasma6-integration-plugin-lang
Recommends:     plasma6-nm-lang
Recommends:     plasma6-pa-lang
Recommends:     plasma6-print-manager-lang
Recommends:     plasma6-systemmonitor-lang
Recommends:     plasma6-thunderbolt-lang
Recommends:     plasma6-vault-lang
Recommends:     plasma6-workspace-lang
Recommends:     plymouth-lang
Recommends:     polkit-kde-agent-6-lang
Recommends:     powerdevil6-lang
Recommends:     procps-lang
Recommends:     psmisc-lang
Recommends:     qqc2-desktop-style-lang
Recommends:     qrca-lang
Recommends:     samba-client-lang
Recommends:     samba-winbind-libs-lang
Recommends:     sddm-kcm6-lang
Recommends:     sed-lang
Recommends:     shared-mime-info-lang
Recommends:     snapper-lang
Recommends:     spectacle-lang
Recommends:     svgpart-lang
Recommends:     system-config-printer-common-lang
Recommends:     systemd-lang
Recommends:     systemsettings6-lang
Recommends:     tar-lang
Recommends:     udisks2-lang
Recommends:     upower-lang
Recommends:     util-linux-lang
Recommends:     wget-lang
Recommends:     wireplumber-lang
Recommends:     xdg-desktop-portal-gtk-lang
Recommends:     xdg-desktop-portal-kde6-lang
Recommends:     xdg-desktop-portal-lang
Recommends:     xdg-user-dirs-lang
Recommends:     xkeyboard-config-lang
Recommends:     xz-lang
Recommends:     zenity-lang

%description -n nazoos-translations
Pulls in the translations (-lang packages) of the programs on the
NazoOS desktop, so the installer's language choice reaches KDE Plasma,
the login screen and password dialogs without a download after the
installation.

%prep
# Nothing to unpack: a pattern only carries dependencies

%build
# Nothing to compile

%install
# A pattern needs at least one file, otherwise the RPM is empty
mkdir -p %{buildroot}%{_docdir}/patterns
echo 'This file marks the pattern nazoos to be installed.' \
  > %{buildroot}%{_docdir}/patterns/nazoos.txt
mkdir -p %{buildroot}%{_docdir}/nazoos-translations
echo 'Meta package: pulls in the -lang packages of the NazoOS desktop.' \
  > %{buildroot}%{_docdir}/nazoos-translations/README

%files
%dir %{_docdir}/patterns
%{_docdir}/patterns/nazoos.txt

%files -n nazoos-translations
%dir %{_docdir}/nazoos-translations
%{_docdir}/nazoos-translations/README

%changelog
