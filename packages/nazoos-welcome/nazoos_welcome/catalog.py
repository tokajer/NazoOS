# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Everything nazoos-welcome may change on the system.

Shared by the GUI and the root helper. The helper only accepts ids from
this file, never package names, paths or commands from the caller.
"""

# Optional apps (ADR 0003). Flatpaks come from Flathub (system-wide),
# RPMs from the Tumbleweed repos. "refs" are installed together.
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
    # enabled after the install, "trusted" interfaces go into firewalld's
    # trusted zone (Android's network: DHCP and DNS from the host)
    {"id": "waydroid", "name": "Waydroid", "category": "gaming",
     "kind": "rpm", "refs": ["waydroid", "nazoos-binder"], "icon": "waydroid",
     "kernel": "nazoos", "units": ["waydroid-container.service"],
     "trusted": ["waydroid0"],
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
     "summary": "Logitech Unifying and Bolt receivers"},
    {"id": "skanpage", "name": "Skanpage", "category": "hardware",
     "kind": "rpm", "refs": ["skanpage"], "icon": "skanpage",
     "summary": "Scan documents, also several pages into one PDF"},
    # Steam Deck only: card on the Gaming page, not on the Apps page
    # (category not in APP_CATEGORIES). Opt-in, because its install
    # script downloads Valve's proprietary dock firmware updater
    {"id": "deckdock", "name": "Steam Deck dock firmware", "category": "handheld",
     "kind": "rpm", "refs": ["jupiter-dock-updater-bin"],
     "icon": "preferences-desktop-peripherals",
     "summary": "Firmware updates for the official Steam Deck dock"},
]

APP_CATEGORIES = ["gaming", "social", "media", "office", "hardware"]

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
# "gpu"/"cpu": only shown on matching hardware (GamingPage.qml)
KERNEL_PARAMS = [
    {"id": "amdgpu-oc", "param": "amdgpu.ppfeaturemask=0xffffffff",
     "gpu": "amd", "warning": False, "name": "AMD GPU overclocking",
     "summary": "Unlocks clock and voltage controls in LACT"},
    {"id": "mitigations-off", "param": "mitigations=off",
     "gpu": None, "warning": True, "name": "Disable CPU mitigations",
     "summary": "A few percent more performance on older CPUs, "
                "but removes protection against Spectre-type attacks"},
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

# USB polling rate per device (kernel-nazoos patch 0022, like Nobara's
# custom-device-pollrates). Kernel option VID:PID:ms[,VID:PID:ms...];
# usbcore is built in, so only the command line keeps it over a restart.
# The sysfs file exists only in kernel-nazoos and holds at most 127 chars.
POLLRATE_PARAM = "usbcore.interrupt_interval_override"
POLLRATE_SYSFS = "/sys/module/usbcore/parameters/interrupt_interval_override"
POLLRATE_MAXLEN = 127
# Interval in ms: 0 = device default, then 125, 250, 500 and 1000 Hz
POLLRATE_INTERVALS = [0, 8, 4, 2, 1]


def pollrate_parse(value):
    """{"045e:028e": 1, ...} from "045e:028e:1,..." (bad entries dropped)."""
    result = {}
    for entry in value.strip().split(","):
        parts = entry.strip().lower().split(":")
        if (len(parts) == 3 and all(len(p) == 4 for p in parts[:2])
                and all(c in "0123456789abcdef" for c in parts[0] + parts[1])
                and parts[2].isdigit() and int(parts[2]) > 0):
            result[f"{parts[0]}:{parts[1]}"] = int(parts[2])
    return result


def pollrate_format(overrides):
    return ",".join(f"{vp}:{ms}" for vp, ms in sorted(overrides.items()))


# sched_ext schedulers offered in the UI (ADR 0002), default first
SCX_SCHEDULERS = ["scx_lavd", "scx_bpfland", "scx_rusty", "scx_flash"]

# Packman: multimedia codecs (DISCLAIMER.md, "Third-party repositories").
# Same mirror and priority as `opi codecs`. Only names Packman really
# ships: the libav* libraries are switched by packman_switch(), not named
# here (versioned names like libavcodec62 change with every FFmpeg major).
# No pipewire-aptx: Tumbleweed's pipewire-spa-plugins has aptX itself
# since 2026-10 (libfreeaptx) and obsoletes the Packman package.
PACKMAN_ALIAS = "packman"
PACKMAN_URL = "https://ftp.fau.de/packman/suse/openSUSE_Tumbleweed/"
PACKMAN_PRIORITY = "70"
PACKMAN_CODECS = [
    "ffmpeg", "vlc-codecs",
    "gstreamer-plugins-bad-codecs", "gstreamer-plugins-ugly-codecs",
    "libfdk-aac2",
]
OSS_CODECS = [
    "gstreamer-plugins-good", "gstreamer-plugins-good-extra",
    "gstreamer-plugins-bad", "gstreamer-plugins-ugly",
    "gstreamer-plugins-libav", "dav1d",
]

# NVIDIA: userspace from NVIDIA's repo (added directly; the package
# openSUSE-repos-Tumbleweed-NVIDIA would switch all repos to zypp services).
# "open": SUSE-signed open kernel module (Secure Boot works), Turing
# (GTX 16, RTX 20) and newer. "legacy": closed G06 module for Maxwell,
# Pascal and Volta (GTX 750 to GTX 10), not signed for Secure Boot.
# The kmp-meta packages pick the module for every installed kernel flavor.
NVIDIA_REPO_ALIAS = "NVIDIA"
NVIDIA_REPO_URL = "https://download.nvidia.com/opensuse/tumbleweed"
NVIDIA_DRIVERS = {
    "open": ["nvidia-open-driver-G07-signed-kmp-meta",
             "nvidia-video-G07", "nvidia-video-G07-32bit",
             "nvidia-gl-G07", "nvidia-gl-G07-32bit",
             "nvidia-compute-utils-G07"],
    "legacy": ["nvidia-driver-G06-kmp-meta",
               "nvidia-video-G06", "nvidia-video-G06-32bit",
               "nvidia-gl-G06", "nvidia-gl-G06-32bit",
               "nvidia-compute-utils-G06"],
}

# ROCm: AMD GPU compute (HIP, OpenCL) for Blender, DaVinci Resolve and local
# AI tools, not needed for games. All from Tumbleweed oss (ADR 0012).
# /dev/kfd gets systemd's uaccess tag: no "render" group for the user.
ROCM_PACKAGES = ["rocm-hip", "rocm-opencl", "rocminfo", "amdsmi"]

# Handheld / Steam Deck pattern (separate package, may not exist yet)
DECK_PATTERN = "nazoos-deck"

# Steam gaming mode (nazoos-session): boot mode file and tools
SESSION_CONF = "/etc/nazoos/session.conf"
SESSION_CTL = "/usr/libexec/nazoos-session/nazoos-session-ctl"
SESSION_DETECT = "/usr/libexec/nazoos-session/nazoos-detect-handheld"

# NazoOS kernel (ADR 0007/0008). Opt-in: the repo is added on install.
# Stage 1 installs kernel-nazoos next to kernel-default, stage 2 removes
# kernel-default with the conflict package nazoos-kernel-only.
KERNEL_REPO_ALIAS = "nazoos-kernel"
KERNEL_REPO_URL = ("https://download.opensuse.org/repositories/"
                   "home:/Tokajer:/nazoos:/kernel/openSUSE_Tumbleweed/")
KERNEL_PACKAGE = "kernel-nazoos"
KERNEL_DEFAULT = "kernel-default"
KERNEL_ONLY_PACKAGE = "nazoos-kernel-only"
# Kernel module packages: <base>-kmp-default from Tumbleweed/NVIDIA,
# <base>-kmp-nazoos from our kernel project. G06 open has no nazoos build
# (ADR 0018); it stays listed so kernel_install stops with a clear error
KMP_BASES = ["nvidia-open-driver-G07-signed", "nvidia-open-driver-G06-signed",
             "xone", "xpadneo"]
# Only built for kernel-default (closed NVIDIA driver from NVIDIA's repo):
# kernel-nazoos would boot without graphics driver
KMP_DEFAULT_ONLY = ["nvidia-driver-G06-kmp-default"]
# Only built for kernel-nazoos, installed and removed with it (<base>-kmp-
# nazoos): acpi_call for handheld TDP tools (Handheld Daemon, SimpleDeckyTDP)
KMP_NAZOOS_ONLY = ["acpi_call"]
# State of the boot counter and the "prefer kernel-nazoos" switch
KERNEL_STATE_DIR = "/var/lib/nazoos"
KERNEL_STABLE_BOOTS = 3

# Drives: file systems offered for automatic mounting, and the marker that
# identifies fstab lines written by nazoos-welcome
AUTOMOUNT_FS = ["ext4", "btrfs", "xfs", "ntfs", "exfat"]
FSTAB_MARKER = "# nazoos-welcome automount"
MOUNT_BASE = "/mnt"

# Repair page (ADR 0012): repos every NazoOS system needs, same aliases and
# URLs as kiwi/nazoos-image/config.sh
STANDARD_REPOS = [
    {"alias": "repo-oss",
     "url": "https://download.opensuse.org/tumbleweed/repo/oss/"},
    {"alias": "repo-non-oss",
     "url": "https://download.opensuse.org/tumbleweed/repo/non-oss/"},
    {"alias": "repo-update",
     "url": "https://download.opensuse.org/update/tumbleweed/"},
]


def repo_path(url):
    """URL path without host: download. and cdn.opensuse.org match."""
    return "/" + url.split("://", 1)[-1].split("/", 1)[-1].rstrip("/") + "/"


# Packages Packman rebuilds with full codecs. A mix of Packman and openSUSE
# builds of these breaks video playback after an update. Mesa: Packman
# "Extra" builds Tumbleweed's Mesa.spec with video codecs (H.264/H.265
# VA-API); packman_switch() moves it too, and a mixed Mesa breaks graphics.
# No gstreamer: Packman only ships gstreamer-plugins-{bad,ugly}-codecs
# (no openSUSE twin), the plain bad/ugly/libav plugins come from oss on
# purpose (OSS_CODECS) and would be a false "mixed" finding.
PACKMAN_FAMILY = (r"(ffmpeg-\d+|lib(avcodec|avdevice|avfilter|avformat|avutil"
                  r"|postproc|swresample|swscale)\d+"
                  r"|Mesa(-dri(-nouveau)?|-libEGL1|-libGL1|-libva"
                  r"|-libRusticlOpenCL|-vulkan-(anti-lag|device-select"
                  r"|overlay))?"
                  r"|libgbm1|libvulkan_[a-z]+)"
                  r"(-32bit)?")
# Failed units the repair page ignores: known harmless upstream issues.
# drkonqi-coredump-pickup (drkonqi6 6.7): RuntimeMaxSec=30min, ends with
# result "timeout" after login although nothing crashed (VM 2026-10-11)
IGNORED_UNITS = {"drkonqi-coredump-pickup.service"}
# Apps started from the menu run as transient units app-<name>@<id>.service
# (or .scope). One fails when the app exits with an error, e.g. a cancelled
# password dialog of a pkexec launcher: not a system problem, and
# restarting it would start the app again
IGNORED_UNIT_PATTERN = r"app-.+@[0-9a-f]+\.(service|scope)"
# Seconds to wait after restarting failed units: a Type=simple unit
# fails again only after "systemctl restart" has returned
UNIT_SETTLE_SECONDS = 3
# Free space below which the repair page warns (whichever is larger)
SPACE_MIN_GB = 5
SPACE_MIN_PERCENT = 5


def by_id(items, item_id):
    for item in items:
        if item["id"] == item_id:
            return item
    return None
