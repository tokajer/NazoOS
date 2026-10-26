# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Everything nazoos-welcome may change on the system.

Shared by the GUI and the root helper. The helper only accepts ids from
this file, never package names, paths or commands from the caller. Repos,
paths and the package lists the user does not pick are in system.py.
"""

# Optional apps (ADR 0003). Flatpaks come from Flathub (system-wide),
# RPMs from the Tumbleweed repos. "refs" are installed together.
# "appstream": component id of the icon in the AppStream caches when
# neither "icon" nor a ref matches it (appicons.py)
APPS = [
    # Gaming
    {"id": "protonupqt", "name": "ProtonUp-Qt", "category": "gaming",
     "kind": "flatpak", "refs": ["net.davidotek.pupgui2"],
     "icon": "net.davidotek.pupgui2",
     "summary": "Install and update Proton-GE and other compatibility tools"},
    {"id": "protonplus", "name": "ProtonPlus", "category": "gaming",
     "kind": "flatpak", "refs": ["com.vysp3r.ProtonPlus"],
     "icon": "com.vysp3r.ProtonPlus",
     "summary": "Alternative manager for Proton and Wine versions"},
    {"id": "heroic", "name": "Heroic Games Launcher", "category": "gaming",
     "kind": "flatpak", "refs": ["com.heroicgameslauncher.hgl"],
     "icon": "com.heroicgameslauncher.hgl",
     "summary": "Epic Games, GOG and Amazon Prime Gaming"},
    {"id": "bottles", "name": "Bottles", "category": "gaming",
     "kind": "flatpak", "refs": ["com.usebottles.bottles"],
     "icon": "com.usebottles.bottles",
     "summary": "Run Windows programs in managed Wine prefixes"},
    {"id": "prismlauncher", "name": "Prism Launcher", "category": "gaming",
     "kind": "flatpak", "refs": ["org.prismlauncher.PrismLauncher"],
     "icon": "org.prismlauncher.PrismLauncher",
     "summary": "Minecraft launcher with mod support"},
    {"id": "retroarch", "name": "RetroArch", "category": "gaming",
     "kind": "flatpak", "refs": ["org.libretro.RetroArch"],
     "icon": "org.libretro.RetroArch",
     "summary": "Emulator frontend for retro consoles"},
    {"id": "moonlight", "name": "Moonlight", "category": "gaming",
     "kind": "flatpak", "refs": ["com.moonlight_stream.Moonlight"],
     "icon": "com.moonlight_stream.Moonlight",
     "summary": "Stream games from another PC"},
    # Linked from Emulators:Waydroid into our OBS project. Needs Binder,
    # which only kernel-nazoos has built in ("kernel"); nazoos-binder
    # stands in for waydroid's "binder-kmp" requirement. "units" are
    # enabled after the install, "firewall" interfaces go into firewalld's
    # zone system.WAYDROID_ZONE (Android's network: DHCP and DNS from the
    # host, no other host service), "setup"
    # names the step root/apps.py runs after the install
    {"id": "waydroid", "name": "Waydroid", "category": "gaming",
     "kind": "rpm", "refs": ["waydroid", "nazoos-binder"], "icon": "waydroid",
     "kernel": "nazoos", "units": ["waydroid-container.service"],
     "firewall": ["waydroid0"], "setup": "waydroid",
     "summary": "Android apps and games in a window. The first start "
                "downloads Android (about 1 GB)"},
    # Communication
    {"id": "discord", "name": "Discord", "category": "social",
     "kind": "flatpak", "refs": ["com.discordapp.Discord"],
     "icon": "com.discordapp.Discord",
     "summary": "Voice and text chat for gamers"},
    {"id": "vesktop", "name": "Vesktop", "category": "social",
     "kind": "flatpak", "refs": ["dev.vencord.Vesktop"],
     "icon": "dev.vencord.Vesktop",
     "summary": "Discord client with working screen sharing on Wayland"},
    {"id": "signal", "name": "Signal", "category": "social",
     "kind": "flatpak", "refs": ["org.signal.Signal"],
     "icon": "org.signal.Signal",
     "summary": "Private messenger with end-to-end encryption"},
    {"id": "teamspeak3", "name": "TeamSpeak 3", "category": "social",
     "kind": "flatpak", "refs": ["com.teamspeak.TeamSpeak3"],
     "icon": "com.teamspeak.TeamSpeak3",
     "summary": "Voice chat on TeamSpeak 3 servers"},
    # Recording and creative
    {"id": "obs", "name": "OBS Studio", "category": "media",
     "kind": "flatpak",
     "refs": ["com.obsproject.Studio",
              "com.obsproject.Studio.Plugin.OBSVkCapture",
              "org.freedesktop.Platform.VulkanLayer.OBSVkCapture"],
     "icon": "com.obsproject.Studio",
     "summary": "Streaming and recording, with Vulkan game capture"},
    {"id": "gsr", "name": "GPU Screen Recorder", "category": "media",
     "kind": "rpm", "refs": ["gpu-screen-recorder-gtk"],
     "icon": "com.dec05eba.gpu_screen_recorder",
     "summary": "Low-overhead recording and instant replay (like ShadowPlay)"},
    {"id": "kdenlive", "name": "Kdenlive", "category": "media",
     "kind": "flatpak", "refs": ["org.kde.kdenlive"], "icon": "kdenlive",
     "summary": "Video editor"},
    {"id": "blender", "name": "Blender", "category": "media",
     "kind": "flatpak", "refs": ["org.blender.Blender"],
     "icon": "org.blender.Blender", "summary": "3D creation suite"},
    {"id": "gimp", "name": "GIMP", "category": "media",
     "kind": "flatpak", "refs": ["org.gimp.GIMP"], "icon": "org.gimp.GIMP",
     "summary": "Image editor"},
    {"id": "krita", "name": "Krita", "category": "media",
     "kind": "flatpak", "refs": ["org.kde.krita"], "icon": "krita",
     "summary": "Digital painting"},
    {"id": "inkscape", "name": "Inkscape", "category": "media",
     "kind": "flatpak", "refs": ["org.inkscape.Inkscape"],
     "icon": "org.inkscape.Inkscape", "summary": "Vector graphics editor"},
    {"id": "vlc", "name": "VLC", "category": "media",
     "kind": "flatpak", "refs": ["org.videolan.VLC"], "icon": "vlc",
     "summary": "Media player with built-in codecs"},
    {"id": "spotify", "name": "Spotify", "category": "media",
     "kind": "flatpak", "refs": ["com.spotify.Client"],
     "icon": "com.spotify.Client", "summary": "Music streaming"},
    # Office and tools
    {"id": "libreoffice", "name": "LibreOffice", "category": "office",
     "kind": "flatpak", "refs": ["org.libreoffice.LibreOffice"],
     "icon": "libreoffice-startcenter",
     "summary": "Office suite (about 600 MB)"},
    {"id": "thunderbird", "name": "Thunderbird", "category": "office",
     "kind": "flatpak", "refs": ["org.mozilla.Thunderbird"],
     "icon": "thunderbird", "summary": "E-mail and calendar"},
    {"id": "flatseal", "name": "Flatseal", "category": "office",
     "kind": "flatpak", "refs": ["com.github.tchx84.Flatseal"],
     "icon": "com.github.tchx84.Flatseal",
     "summary": "Manage Flatpak permissions"},
    {"id": "warehouse", "name": "Warehouse", "category": "office",
     "kind": "flatpak", "refs": ["io.github.flattool.Warehouse"],
     "icon": "io.github.flattool.Warehouse",
     "summary": "Manage installed Flatpaks, their data and old versions"},
    {"id": "gearlever", "name": "Gear Lever", "category": "office",
     "kind": "rpm", "refs": ["gearlever"], "icon": "it.mijorus.gearlever",
     "summary": "Add AppImages to the app menu and keep them updated"},
    {"id": "isoimagewriter", "name": "ISO Image Writer", "category": "office",
     "kind": "flatpak", "refs": ["org.kde.isoimagewriter"],
     "icon": "org.kde.isoimagewriter",
     "summary": "Write ISO images to USB sticks"},
    {"id": "meld", "name": "Meld", "category": "office",
     "kind": "rpm", "refs": ["meld"], "icon": "org.gnome.Meld",
     "summary": "Compare files and folders"},
    # Plugin for the network settings, no app of its own
    {"id": "openvpn", "name": "OpenVPN", "category": "office",
     "kind": "rpm", "refs": ["NetworkManager-openvpn", "plasma6-nm-openvpn"],
     "icon": "network-vpn",
     "summary": "OpenVPN connections in the network settings "
                "(WireGuard works without it)"},
    # Hardware
    {"id": "piper", "name": "Piper", "category": "hardware",
     "kind": "rpm", "refs": ["piper"], "icon": "org.freedesktop.Piper",
     "summary": "Configure gaming mice (buttons, DPI, LEDs)"},
    {"id": "solaar", "name": "Solaar", "category": "hardware",
     "kind": "rpm", "refs": ["solaar"], "icon": "solaar",
     "appstream": "io.github.pwr_solaar.solaar",
     "summary": "Logitech Unifying and Bolt receivers"},
    {"id": "skanpage", "name": "Skanpage", "category": "hardware",
     "kind": "rpm", "refs": ["skanpage"], "icon": "skanpage",
     "appstream": "org.kde.skanpage",
     "summary": "Scan documents, also several pages into one PDF"},
    {"id": "hplip", "name": "HPLIP", "category": "hardware",
     "kind": "rpm", "refs": ["hplip"], "icon": "printer",
     "summary": "Drivers for HP printers and scanners"},
    # Steam Deck only: card on the Gaming page, not on the Apps page
    # (category in HIDDEN_CATEGORIES). Opt-in, because its install
    # script downloads Valve's proprietary dock firmware updater
    {"id": "deckdock", "name": "Steam Deck dock firmware", "category": "handheld",
     "kind": "rpm", "refs": ["jupiter-dock-updater-bin"],
     "icon": "preferences-desktop-peripherals",
     "summary": "Firmware updates for the official Steam Deck dock"},
]

APP_CATEGORIES = ["gaming", "social", "media", "office", "hardware"]
# Categories whose apps have their own card elsewhere, not on the Apps page
# (deckdock: Gaming page, Steam Deck only)
HIDDEN_CATEGORIES = {"handheld"}

# systemd services that can be switched on and off.
# "package" is installed first if it is missing; "user" units run per user.
SERVICES = [
    {"id": "bluetooth", "unit": "bluetooth.service", "package": "bluez",
     "user": False, "name": "Bluetooth",
     "summary": "Wireless controllers, headsets, mice and keyboards"},
    {"id": "lactd", "unit": "lactd.service", "package": "lact",
     "user": False, "name": "LACT daemon",
     "summary": "Needed by LACT to change GPU clocks, power and fans"},
    {"id": "coolercontrold", "unit": "coolercontrold.service",
     "package": "coolercontrol", "user": False, "name": "CoolerControl",
     "summary": "Fan curves and cooling devices"},
    {"id": "sshd", "unit": "sshd.service", "package": "openssh-server",
     "user": False, "name": "SSH server",
     "summary": "Remote login from other computers (advanced)"},
    {"id": "psd", "unit": "psd.service", "package": "profile-sync-daemon",
     "user": True, "name": "Profile-sync-daemon",
     "summary": "Keeps browser profiles in RAM: faster, less disk wear"},
]

# Kernel command line options, written to GRUB_CMDLINE_LINUX_DEFAULT.
# "gpu"/"cpu": only shown on matching hardware (probes.kparam_shown)
KERNEL_PARAMS = [
    {"id": "amdgpu-oc", "param": "amdgpu.ppfeaturemask=0xffffffff",
     "gpu": "amd", "warning": False, "name": "AMD GPU overclocking",
     "summary": "Unlocks clock and voltage controls in LACT"},
    {"id": "mitigations-off", "param": "mitigations=off",
     "gpu": None, "warning": True, "name": "Disable CPU mitigations",
     "summary": "A few percent more performance on older CPUs, "
                "but removes protection against Spectre-type attacks",
     "confirm": {
         "title": "Disable CPU security mitigations?",
         "text": "This removes protection against Spectre, Meltdown and "
                 "similar CPU attacks. Malicious websites or programs could "
                 "read data from other programs. Only do this if you know "
                 "the risk.",
         "ok": "Disable mitigations"}},
    # kernel-nazoos only (0008-0014 patches); kernel-default ignores it.
    # Shown on CPUs without the tsc_adjust flag (most AMD CPUs incl. the
    # Steam Deck). Not on by default: it writes the TSC directly
    {"id": "tsc-directsync", "param": "tsc=directsync",
     "gpu": None, "cpu": "no-tsc-adjust", "warning": False,
     "name": "Stable CPU clock after standby",
     "summary": "Helps when games stutter after waking up or the system "
                "clock falls back to HPET (Steam Deck, some AMD systems). "
                "Needs the NazoOS kernel"},
]

# sched_ext schedulers offered in the UI (ADR 0002), default first
SCX_SCHEDULERS = ["scx_lavd", "scx_bpfland", "scx_rusty", "scx_flash"]

# Root actions of the helper, with the text shown while they run
ACTION_LABELS = {
    "codecs-install": "Installing multimedia codecs",
    "nvidia-install": "Installing the NVIDIA driver",
    "scx-enable": "Enabling the scheduler",
    "scx-disable": "Disabling the scheduler",
    "kparam": "Changing kernel options",
    "pollrate": "Changing the USB polling rate",
    "rocm-install": "Installing ROCm",
    "rocm-remove": "Removing ROCm",
    "deck-install": "Installing the handheld pattern",
    "session-boot-mode": "Changing the start mode",
    "kernel-install": "Installing the NazoOS kernel",
    "kernel-only": "Removing the openSUSE kernel",
    "kernel-restore": "Switching back to the openSUSE kernel",
    "kernel-remove": "Removing the NazoOS kernel",
    "mok-import": "Preparing the Secure Boot key",
    "app-install": "Installing",
    "app-remove": "Removing",
    "service": "Changing service",
    "system-update": "Updating the system",
    "repo-refresh": "Refreshing repositories",
    "cache-clean": "Cleaning the package cache",
    "flatpak-unused": "Removing unused Flatpak runtimes",
    "flatpak-repair": "Repairing Flatpak",
    "snapshot": "Creating a snapshot",
    "channel": "Switching the update channel",
    "repair-repos": "Repairing repositories",
    "repair-key": "Trusting the repository key",
    "repair-rpmdb": "Rebuilding the package database",
    "repair-deps": "Installing missing dependencies",
    "repair-packman": "Switching codecs to Packman",
    "repair-nvidia": "Reinstalling the NVIDIA kernel module",
    "repair-units": "Restarting failed services",
    "repair-space": "Freeing disk space",
    "repair-flathub": "Adding Flathub",
    "repair-boot": "Rebuilding boot files",
    "automount-add": "Adding drive",
    "automount-remove": "Removing drive",
}


def by_id(items, item_id):
    for item in items:
        if item["id"] == item_id:
            return item
    return None
