# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-branding
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        NazoOS desktop branding and defaults
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
# Owns /usr/share/icons/hicolor/* (build check: no unowned directories)
BuildRequires:  hicolor-icon-theme
Requires:       hicolor-icon-theme
Requires:       breeze6-cursors
Requires:       breeze6-style
Requires:       kf6-breeze-icons
Requires:       plasma6-workspace
# Login screen theme (plasma6-branding-openSUSE pulled it in before):
# upstream Breeze, packaged by openSUSE under this
# name; we only override background and logo (theme.conf.user, ADR 0019)
Requires:       (plasma6-sddm-theme-openSUSE if sddm)
# Both ship /etc/xdg/kdeglobals; ours replaces openSUSE's Plasma defaults
Conflicts:      plasma6-branding-openSUSE
# Boot splash and boot menu (subpackages below)
Recommends:     %{name}-plymouth
Recommends:     %{name}-grub2
# Fonts for the GRUB theme (grub2-mkfont)
BuildRequires:  dejavu-fonts
BuildRequires:  grub2
# /etc/os-release is rewritten after every openSUSE-release update
Requires(post): coreutils
Requires(post): sed

%description
Desktop defaults for NazoOS: the NazoOS global theme for KDE Plasma
(Breeze Dark with the NazoOS wallpaper, also on the lock and login
screen), Breeze cursors (also as system default cursor theme), the
NazoOS website in System Settings, tearing allowed for fullscreen games
and file indexing limited to file names. /etc/os-release names the
system NazoOS (based on openSUSE-release, ID stays opensuse-tumbleweed),
so does the console login banner.

%package plymouth
Summary:        NazoOS boot splash (Plymouth theme)
Requires:       plymouth-plugin-two-step
# Spinner images (ImageDir of the theme)
Requires:       plymouth-theme-spinner
Provides:       plymouth-branding = %{version}
Conflicts:      plymouth-branding-openSUSE
Supplements:    (plymouth and %{name})

%description plymouth
Plymouth boot splash of NazoOS: the NazoOS logo with a spinner on a dark
background. Replaces openSUSE's default splash.

%package grub2
Summary:        NazoOS boot menu (GRUB theme)
Requires:       grub2
# flock: activate-theme shares the lock of the Python grub writers
Requires(post): util-linux
Provides:       grub2-branding = %{version}
Conflicts:      grub2-branding-openSUSE
Supplements:    (grub2 and %{name})

%description grub2
GRUB theme of NazoOS: wallpaper background, logo and a readable boot
menu (also for the snapshot entries). Replaces openSUSE's GRUB theme.

%prep
%autosetup

%build
# GRUB bitmap fonts (theme.txt names them "DejaVu Sans Regular 14" etc.)
for size in 12 14; do
  grub2-mkfont -s $size -o grub2/DejaVuSans$size.pf2 \
    %{_datadir}/fonts/truetype/DejaVuSans.ttf
done
for size in 14 24; do
  grub2-mkfont -s $size -o grub2/DejaVuSans-Bold$size.pf2 \
    %{_datadir}/fonts/truetype/DejaVuSans-Bold.ttf
done

%install
install -Dm0644 -t %{buildroot}%{_sysconfdir}/xdg \
  xdg/kdeglobals xdg/kcminputrc xdg/kcm-about-distrorc xdg/kscreenlockerrc \
  xdg/kwinrc xdg/baloofilerc
install -Dm0644 -t %{buildroot}%{_datadir}/wallpapers/NazoOS wallpaper/NazoOS/metadata.json
install -Dm0644 -t %{buildroot}%{_datadir}/wallpapers/NazoOS/contents/images \
  wallpaper/NazoOS/contents/images/*.png
install -Dm0644 -t %{buildroot}%{_datadir}/plasma/look-and-feel/org.nazoos.desktop \
  look-and-feel/org.nazoos.desktop/metadata.json
install -Dm0644 -t %{buildroot}%{_datadir}/plasma/look-and-feel/org.nazoos.desktop/contents \
  look-and-feel/org.nazoos.desktop/contents/defaults
install -Dm0644 sddm/theme.conf.user \
  %{buildroot}%{_datadir}/sddm/themes/breeze-openSUSE/theme.conf.user
install -Dm0644 logo/nazoos-logo.svg \
  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/nazoos-logo.svg
install -Dm0644 icons/index.theme %{buildroot}%{_datadir}/icons/default/index.theme
install -Dm0755 os-release/nazoos-os-release \
  %{buildroot}%{_libexecdir}/nazoos-branding/nazoos-os-release
# Console login banner: agetty reads /usr/lib/issue.d, a file with the
# same name in /etc/issue.d replaces openSUSE-release's "Welcome to
# openSUSE Tumbleweed". \S = PRETTY_NAME from os-release (NazoOS)
install -Dm0644 issue/10-openSUSE.issue \
  %{buildroot}%{_sysconfdir}/issue.d/10-openSUSE.issue
# Plymouth
install -Dm0644 -t %{buildroot}%{_datadir}/plymouth/themes/nazoos \
  plymouth/nazoos.plymouth plymouth/watermark.png
install -Dm0644 plymouth/plymouthd.defaults %{buildroot}%{_datadir}/plymouth/plymouthd.defaults
# GRUB
install -Dm0644 -t %{buildroot}%{_datadir}/grub2/themes/nazoos \
  grub2/theme.txt grub2/background.jpg grub2/*.png grub2/*.pf2
install -Dm0755 grub2/activate-theme %{buildroot}%{_datadir}/grub2/themes/nazoos/activate-theme

%post
%{_libexecdir}/nazoos-branding/nazoos-os-release || :

# openSUSE-release installed or updated: its /etc/os-release symlink is
# back, write ours again
%triggerin -- openSUSE-release
%{_libexecdir}/nazoos-branding/nazoos-os-release || :

%postun
if [ $1 -eq 0 ]; then
  ln -sfn ../usr/lib/os-release %{_sysconfdir}/os-release || :
fi

%post plymouth
%{?regenerate_initrd_post}

%postun plymouth
%{?regenerate_initrd_post}

%posttrans plymouth
%{?regenerate_initrd_posttrans}

%post grub2
%{_datadir}/grub2/themes/nazoos/activate-theme || :
# grub.cfg is regenerated once at the end of the transaction
mkdir -p /run/update-bootloader && touch /run/update-bootloader/refresh || :

%postun grub2
if [ $1 -eq 0 ]; then
  rm -rf /boot/grub2/themes/nazoos
  # Only lines that still point at our theme: a replacing branding package
  # (grub2-branding-openSUSE) has already set its own in its %%post
  if [ -f /etc/default/grub ]; then
    # Same lock as activate-theme and the Python grub writers
    flock -w 60 /run/nazoos-grub.lock \
      sed -i -E '/^GRUB_(THEME|BACKGROUND)=.*\/themes\/nazoos\//d' /etc/default/grub || :
    [ -x /sbin/update-bootloader ] && /sbin/update-bootloader --refresh || :
  fi
fi

%posttrans grub2
if [ -x /sbin/update-bootloader ] && [ -f /run/update-bootloader/refresh ]; then
  rm -f /run/update-bootloader/refresh
  /sbin/update-bootloader --refresh || :
fi

%files
%config(noreplace) %{_sysconfdir}/xdg/kdeglobals
%config(noreplace) %{_sysconfdir}/xdg/kcminputrc
%config(noreplace) %{_sysconfdir}/xdg/kcm-about-distrorc
%config(noreplace) %{_sysconfdir}/xdg/kscreenlockerrc
%config(noreplace) %{_sysconfdir}/xdg/kwinrc
%config(noreplace) %{_sysconfdir}/xdg/baloofilerc
%dir %{_datadir}/wallpapers
%{_datadir}/wallpapers/NazoOS
%dir %{_datadir}/plasma
%dir %{_datadir}/plasma/look-and-feel
%{_datadir}/plasma/look-and-feel/org.nazoos.desktop
%dir %{_datadir}/sddm
%dir %{_datadir}/sddm/themes
%dir %{_datadir}/sddm/themes/breeze-openSUSE
%{_datadir}/sddm/themes/breeze-openSUSE/theme.conf.user
%{_datadir}/icons/hicolor/scalable/apps/nazoos-logo.svg
%dir %{_datadir}/icons/default
%{_datadir}/icons/default/index.theme
%{_libexecdir}/nazoos-branding
%dir %{_sysconfdir}/issue.d
%config(noreplace) %{_sysconfdir}/issue.d/10-openSUSE.issue

%files plymouth
%dir %{_datadir}/plymouth
%dir %{_datadir}/plymouth/themes
%{_datadir}/plymouth/themes/nazoos
%{_datadir}/plymouth/plymouthd.defaults

%files grub2
%dir %{_datadir}/grub2
%dir %{_datadir}/grub2/themes
%{_datadir}/grub2/themes/nazoos

%changelog
