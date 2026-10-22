# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where packages come from and where other tools keep their files (no Qt).
The texts shown to the user are in catalog.py (po/update-pot.sh reads it).
"""

# Waydroid renders with Mesa on the first render node that is not NVIDIA
# (gralloc gbm, egl mesa). In a VM that node has no 3D driver (virtio-gpu
# without virgl, vmwgfx, ...): surfaceflinger crashes in a loop and
# Android never finishes booting (VM 2026-10-15). There the helper sets
# these properties in Waydroid's config: software rendering. Pure NVIDIA
# systems need nothing, Waydroid skips the nvidia node and falls back to
# the same values itself (tools/helpers/lxc.py, make_base_props)
WAYDROID_CONFIG = "/var/lib/waydroid/waydroid.cfg"
WAYDROID_ROOTFS = "/var/lib/waydroid/rootfs"
WAYDROID_SOFTWARE = {"ro.hardware.gralloc": "default",
                     "ro.hardware.egl": "swiftshader"}

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

# ROCm: AMD GPU compute (HIP, OpenCL) for Blender, DaVinci Resolve and local
# AI tools, not needed for games. All from Tumbleweed oss (ADR 0012).
# /dev/kfd gets systemd's uaccess tag: no "render" group for the user.
ROCM_PACKAGES = ["rocm-hip", "rocm-opencl", "rocminfo", "amdsmi"]

# Handheld / Steam Deck pattern (separate package, may not exist yet)
DECK_PATTERN = "nazoos-deck"

# Steam gaming mode (nazoos-session): tools
SESSION_CTL = "/usr/libexec/nazoos-session/nazoos-session-ctl"
SESSION_DETECT = "/usr/libexec/nazoos-session/nazoos-detect-handheld"

# Repair page (ADR 0012): the repos of openSUSE-repos-Tumbleweed (zypp
# service "openSUSE", aliases openSUSE:repo-oss ...). Matched by URL path, so
# cdn./download. hosts and the old plain repo files both count; the aliases
# name the finding and are only added by hand when no service provides them
STANDARD_REPOS = [
    {"alias": "repo-oss",
     "url": "https://download.opensuse.org/tumbleweed/repo/oss/"},
    {"alias": "repo-non-oss",
     "url": "https://download.opensuse.org/tumbleweed/repo/non-oss/"},
    {"alias": "repo-update",
     "url": "https://download.opensuse.org/update/tumbleweed/"},
]
# NazoOS repo of either channel (service "nazoos", ADR 0028)
NAZOOS_REPO_PATHS = [
    "/repositories/home:/Tokajer:/nazoos:/devel/openSUSE_Tumbleweed/",
    "/repositories/home:/Tokajer:/nazoos:/release/openSUSE_Tumbleweed/",
]
# Update channel (ADR 0025/0028): this symlink of nazoos-repos points the
# service "nazoos" at :release (stable) or :devel (beta)
CHANNEL_LINK = "/usr/share/zypp/local/service/nazoos/repo/repoindex.xml"
CHANNEL_REPO_PATHS = {"beta": NAZOOS_REPO_PATHS[0],
                      "stable": NAZOOS_REPO_PATHS[1]}
# zypp services (ADR 0028) that own these repos: a plain addrepo would be
# moved away or duplicated by the next package update. "seed" is a repo
# the package can be installed from when the service and its repos are gone
REPO_SERVICES = [
    {"name": "openSUSE", "package": "openSUSE-repos-Tumbleweed",
     "dir": "/usr/share/zypp/local/service/openSUSE",
     "seed": "https://download.opensuse.org/tumbleweed/repo/oss/"},
    {"name": "nazoos", "package": "nazoos-repos",
     "dir": "/usr/share/zypp/local/service/nazoos",
     "seed": "https://download.opensuse.org" + NAZOOS_REPO_PATHS[0]},
]


# Packages Packman rebuilds with full codecs. A mix of Packman and openSUSE
# builds of these breaks video playback after an update. Mesa: Packman
# "Extra" builds Tumbleweed's Mesa.spec with video codecs (H.264/H.265
# VA-API); packman_switch() moves it too, and a mixed Mesa breaks graphics.
# No gstreamer: Packman only ships gstreamer-plugins-{bad,ugly}-codecs
# (no openSUSE twin), the plain bad/ugly/libav plugins come from oss on
# purpose (OSS_CODECS) and would be a false "mixed" finding.
# Matches ffmpeg-7, libavcodec62-32bit, Mesa-dri, libvulkan_radeon; not
# ffmpeg-7-devel or gstreamer-plugins-bad.
PACKMAN_FAMILY = (r"(ffmpeg-\d+|lib(avcodec|avdevice|avfilter|avformat|avutil"
                  r"|postproc|swresample|swscale)\d+"
                  r"|Mesa(-dri(-nouveau)?|-libEGL1|-libGL1|-libva"
                  r"|-libRusticlOpenCL|-vulkan-(anti-lag|device-select"
                  r"|overlay))?"
                  r"|libgbm1|libvulkan_[a-z]+)"
                  r"(-32bit)?")
