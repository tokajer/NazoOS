# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           nazoos-welcome
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        First steps after installing NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildRequires:  desktop-file-utils
BuildRequires:  gettext-tools
# %check imports the helper's actions
BuildRequires:  nazoos-common
BuildRequires:  python3
BuildRequires:  systemd-rpm-macros
BuildArch:      noarch
# GUI: Python + Qt Quick + Kirigami, native Plasma look
Requires:       kf6-kirigami-imports
Requires:       kf6-qqc2-desktop-style
Requires:       python3
Requires:       python3-pyside6
Requires:       qt6-declarative-imports
# Helper frame, error messages, MOK check, kernel opt-in state (ADR 0030)
Requires:       nazoos-common
# Root actions via pkexec + our Polkit policy
Requires:       polkit
# System probes (lspci, lsblk/findmnt) and actions
Requires:       pciutils
Requires:       util-linux
Requires:       zypper
Recommends:     flatpak
# Secure Boot state and key enrollment for the NazoOS kernel: the
# MokManager password hash (openssl passwd -6) and the certificate from
# the downloaded kernel package (rpm2cpio | cpio), ADR 0024
Recommends:     mokutil
Requires:       cpio
Requires:       openssl
Recommends:     nazoos-branding
Recommends:     snapper
%{?systemd_ordering}

%description
NazoOS Welcome sets up a fresh NazoOS installation without a terminal:
NVIDIA driver, multimedia codecs from Packman, sched_ext scheduler,
kernel options, the optional NazoOS kernel, optional apps from Flathub, automatic mounting of extra
drives, system services, updates, snapshots and maintenance.
Root actions run through a small helper started with pkexec, which
only accepts a fixed list of actions.

%prep
%autosetup

%build
for po in po/*.po; do
  lang=$(basename "$po" .po)
  mkdir -p "locale/$lang/LC_MESSAGES"
  msgfmt --check -o "locale/$lang/LC_MESSAGES/%{name}.mo" "$po"
done

%install
install -Dm0755 nazoos-welcome %{buildroot}%{_bindir}/nazoos-welcome
install -Dm0755 helper/nazoos-welcome-helper \
  %{buildroot}%{_libexecdir}/nazoos-welcome/nazoos-welcome-helper
install -Dm0755 helper/nazoos-kernel-boot \
  %{buildroot}%{_libexecdir}/nazoos-welcome/nazoos-kernel-boot
install -Dm0755 data/grub.d/15_nazoos_fallback \
  %{buildroot}%{_sysconfdir}/grub.d/15_nazoos_fallback
install -Dm0644 data/nazoos-kernel-boot.service \
  %{buildroot}%{_unitdir}/nazoos-kernel-boot.service
install -Dm0644 data/90-nazoos-welcome.preset \
  %{buildroot}%{_presetdir}/90-nazoos-welcome.preset
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/nazoos_welcome \
  nazoos_welcome/*.py
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/nazoos_welcome/root \
  nazoos_welcome/root/*.py
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml qml/*.qml
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml/components \
  qml/components/*.qml
install -Dm0644 -t %{buildroot}%{_datadir}/nazoos-welcome/qml/pages \
  qml/pages/*.qml
install -Dm0644 data/org.nazoos.welcome.desktop \
  %{buildroot}%{_datadir}/applications/org.nazoos.welcome.desktop
install -Dm0644 data/nazoos-welcome-autostart.desktop \
  %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
install -Dm0644 data/org.nazoos.welcome.policy \
  %{buildroot}%{_datadir}/polkit-1/actions/org.nazoos.welcome.policy
cp -a locale %{buildroot}%{_datadir}/
# Byte-compile at build time: users cannot write __pycache__ below /usr
python3 -m compileall -q --invalidation-mode checked-hash \
  -d %{_datadir}/nazoos-welcome/nazoos_welcome \
  %{buildroot}%{_datadir}/nazoos-welcome/nazoos_welcome
%find_lang %{name}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.nazoos.welcome.desktop
desktop-file-validate %{buildroot}%{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" helper/nazoos-kernel-boot
# A helper action without label is silently ignored by the GUI; a label
# without action fails at runtime. The helper itself is syntax-checked by
# running it below.
python3 -B - <<'PY'
import runpy
from nazoos_welcome import catalog
actions = set(runpy.run_path("helper/nazoos-welcome-helper")["ACTIONS"])
known = set(catalog.ACTION_LABELS) | catalog.INTERNAL_ACTIONS
missing, extra = known - actions, actions - known
if missing or extra:
    raise SystemExit("helper ACTIONS mismatch: label without action "
                     f"{sorted(missing)}, action without label "
                     f"{sorted(extra)}")
PY

%pre
%service_add_pre nazoos-kernel-boot.service

%post
%service_add_post nazoos-kernel-boot.service

%preun
%service_del_preun nazoos-kernel-boot.service

%postun
%service_del_postun_without_restart nazoos-kernel-boot.service

# Kernel installed or removed, by any tool (zypper, nazoos-update,
# Discover): keep the chosen kernel behind the top boot menu entry
# (GRUB_TOP_LEVEL names a version, ADR 0008). Runs once per transaction,
# after the kernel scriptlets; does nothing without kernel-nazoos
%transfiletriggerin -- /usr/lib/modules
%{_libexecdir}/nazoos-welcome/nazoos-kernel-boot --grub-only >/dev/null 2>&1 || :

%transfiletriggerpostun -- /usr/lib/modules
%{_libexecdir}/nazoos-welcome/nazoos-kernel-boot --grub-only >/dev/null 2>&1 || :

%files -f %{name}.lang
%{_bindir}/nazoos-welcome
%dir %{_libexecdir}/nazoos-welcome
%{_libexecdir}/nazoos-welcome/nazoos-welcome-helper
%{_libexecdir}/nazoos-welcome/nazoos-kernel-boot
%{_unitdir}/nazoos-kernel-boot.service
# Owned by grub2 too; a fallback to kernel-default while kernel-nazoos
# is the top boot entry (ADR 0008)
%dir %{_sysconfdir}/grub.d
%config %{_sysconfdir}/grub.d/15_nazoos_fallback
%{_presetdir}/90-nazoos-welcome.preset
%{_datadir}/nazoos-welcome
%{_datadir}/applications/org.nazoos.welcome.desktop
%config(noreplace) %{_sysconfdir}/xdg/autostart/nazoos-welcome.desktop
%dir %{_datadir}/polkit-1
%dir %{_datadir}/polkit-1/actions
%{_datadir}/polkit-1/actions/org.nazoos.welcome.policy

%changelog
