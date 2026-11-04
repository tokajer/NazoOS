# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where packages come from and where other tools keep their files (no Qt).
The texts shown to the user are in catalog.py (po/update-pot.sh reads it).
"""

import os
from pathlib import Path

from nazoos_common import repos

# Waydroid renders with Mesa on the first render node that is not NVIDIA
# (gralloc gbm, egl mesa). In a VM that node has no 3D driver (virtio-gpu
# without virgl, vmwgfx, ...): surfaceflinger crashes in a loop and
# Android never finishes booting (VM 2026-10-15). There the helper sets
# these properties in Waydroid's config: software rendering. Pure NVIDIA
# systems need nothing, Waydroid skips the nvidia node and falls back to
# the same values itself (tools/helpers/lxc.py, make_base_props)
WAYDROID_CONFIG = "/var/lib/waydroid/waydroid.cfg"
# firewalld zone of nazoos-tweaks for Waydroid's bridge (DHCP/DNS from the
# host, internet, no other host service)
WAYDROID_ZONE = "nazoos-waydroid"
WAYDROID_ROOTFS = "/var/lib/waydroid/rootfs"
WAYDROID_SOFTWARE = {"ro.hardware.gralloc": "default",
                     "ro.hardware.egl": "swiftshader"}

# Packman: multimedia codecs (DISCLAIMER.md, "Third-party repositories").
# Same mirror and priority as `opi codecs`. Only names Packman really
# ships: the libav* libraries are switched by packman_switch(), not named
# here (versioned names like libavcodec62 change with every FFmpeg major).
# The ffmpeg command line tools are not named either: packman_switch() moves
# the installed ffmpeg-N to Packman; "ffmpeg" would pull the next major
# (conflicts with ffmpeg-8, 2026-10) and the capability ffmpeg-tools has
# providers from ffmpeg-3 on.
# No pipewire-aptx: openSUSE's pipewire-spa-plugins has aptX itself
# since 2026-10 (libfreeaptx) and obsoletes the Packman package.
# The URL per base: BASES.
PACKMAN_ALIAS = "packman"
PACKMAN_PRIORITY = "70"
# Signing keys of the opt-in repos, shipped in repo-keys/ and pinned by
# .github/workflows/rpm-key.yml (ADR 0031). Not in /usr/lib/rpm/gnupg/keys:
# the image imports every key there, these only count once the user
# adds the repo.
REPO_KEYS = Path("/usr/share/nazoos-welcome/repo-keys")
PACKMAN_KEY = REPO_KEYS / "packman.asc"
PACKMAN_CODECS = [
    "vlc-codecs", "gstreamer-plugins-bad-codecs",
    "gstreamer-plugins-ugly-codecs", "libfdk-aac2",
]
OSS_CODECS = [
    "gstreamer-plugins-good", "gstreamer-plugins-good-extra",
    "gstreamer-plugins-bad", "gstreamer-plugins-ugly",
    "gstreamer-plugins-libav", "dav1d",
]

# NVIDIA: userspace from NVIDIA's repo (added directly; the package
# openSUSE-repos-<Base>-NVIDIA would switch all repos to zypp services).
# NVIDIA has no Slowroll repo: Slowroll takes the Tumbleweed one too.
# "open": SUSE-signed open kernel module (Secure Boot works), Turing
# (GTX 16, RTX 20) and newer. "legacy": closed G06 module for Maxwell,
# Pascal and Volta (GTX 750 to GTX 10), not signed for Secure Boot.
# The kmp-meta packages pick the module for every installed kernel flavor.
NVIDIA_REPO_ALIAS = "NVIDIA"
NVIDIA_REPO_URL = "https://download.nvidia.com/opensuse/tumbleweed"
NVIDIA_KEY = REPO_KEYS / "nvidia.asc"
# The variants the user picks. "module": the kernel module base (the meta
# package is "<module>-kmp-meta"); "video": the package that marks the
# variant as installed
NVIDIA_DRIVERS = {
    "open": {"module": "nvidia-open-driver-G07-signed",
             "video": "nvidia-video-G07",
             "packages": ["nvidia-open-driver-G07-signed-kmp-meta",
                          "nvidia-video-G07", "nvidia-video-G07-32bit",
                          "nvidia-gl-G07", "nvidia-gl-G07-32bit",
                          "nvidia-compute-utils-G07"]},
    "legacy": {"module": "nvidia-driver-G06",
               "video": "nvidia-video-G06",
               "packages": ["nvidia-driver-G06-kmp-meta",
                            "nvidia-video-G06", "nvidia-video-G06-32bit",
                            "nvidia-gl-G06", "nvidia-gl-G06-32bit",
                            "nvidia-compute-utils-G06"]},
}

# ROCm: AMD GPU compute (HIP, OpenCL) for Blender, DaVinci Resolve and local
# AI tools, not needed for games. All from openSUSE oss (ADR 0012).
# /dev/kfd gets systemd's uaccess tag: no "render" group for the user.
ROCM_PACKAGES = ["rocm-hip", "rocm-opencl", "rocminfo", "amdsmi"]

# Handheld / Steam Deck pattern (separate package, may not exist yet)
DECK_PATTERN = "nazoos-deck"

# sched_ext: the scx package reads its scheduler from here
SCX_DEFAULT = Path("/etc/default/scx")

# Steam gaming mode (nazoos-session): tools
SESSION_CTL = "/usr/libexec/nazoos-session/nazoos-session-ctl"
SESSION_DETECT = "/usr/libexec/nazoos-session/nazoos-detect-handheld"

# Per base (repos.base()). "repos": those of openSUSE-repos-<Base> (zypp
# service "openSUSE", aliases openSUSE:repo-oss ...) for the Repair page.
# Matched by URL path, so cdn./download. hosts and the old plain repo files
# both count; the aliases name the finding and are only added by hand when
# no service provides them
BASES = {
    "tumbleweed": {
        "name": "Tumbleweed",
        "repos": [
            {"alias": "repo-oss",
             "url": "https://download.opensuse.org/tumbleweed/repo/oss/"},
            {"alias": "repo-non-oss",
             "url": "https://download.opensuse.org/tumbleweed/repo/non-oss/"},
            {"alias": "repo-update",
             "url": "https://download.opensuse.org/update/tumbleweed/"},
        ],
        "packman": "https://ftp.fau.de/packman/suse/openSUSE_Tumbleweed/",
    },
    "slowroll": {
        "name": "Slowroll",
        "repos": [
            {"alias": "repo-oss",
             "url": "https://download.opensuse.org/slowroll/repo/oss/"},
            {"alias": "repo-non-oss",
             "url": "https://download.opensuse.org/slowroll/repo/non-oss/"},
            {"alias": "repo-update",
             "url": "https://download.opensuse.org/update/slowroll/repo/oss/"},
        ],
        "packman": "https://ftp.fau.de/packman/suse/openSUSE_Slowroll/",
    },
}


def base_name(base=None):
    """"Tumbleweed" or "Slowroll" (user texts, snapshot descriptions)."""
    return BASES[base or repos.base()]["name"]


def standard_repos(base=None):
    return BASES[base or repos.base()]["repos"]


def oss_url(base=None):
    return standard_repos(base)[0]["url"]


def packman_url(base=None):
    return BASES[base or repos.base()]["packman"]


# Update channel (ADR 0025/0028) and its OBS project. The symlink
# CHANNEL_LINK of nazoos-repos points the service "nazoos" at :release
# (stable) or :devel (beta)
CHANNEL_PROJECTS = {"beta": "devel", "stable": "release"}
CHANNEL_LINK = "/usr/share/zypp/local/service/nazoos/repo/repoindex.xml"


def current_channel():
    """"stable", "beta" or "" (nazoos-repos missing or link unknown)."""
    try:
        target = os.readlink(CHANNEL_LINK)
    except OSError:
        return ""
    for name in CHANNEL_PROJECTS:
        if target == f"nazoos-{name}-repoindex.xml":
            return name
    return ""


def channel_repo_paths(base=None):
    """{channel: URL path of its NazoOS repo} (service "nazoos", ADR 0028)."""
    obs = repos.OBS_REPOS[base or repos.base()]
    return {channel: f"/repositories/home:/Tokajer:/nazoos:/{project}/{obs}/"
            for channel, project in CHANNEL_PROJECTS.items()}


def nazoos_repo_paths(base=None):
    """The NazoOS repo of either channel."""
    return list(channel_repo_paths(base).values())


def repo_services(base=None):
    """zypp services (ADR 0028) that own the repos: a plain addrepo would
    be moved away or duplicated by the next package update. "seed" is a
    repo the package can be installed from when the service and its repos
    are gone."""
    base = base or repos.base()
    return [
        {"name": "openSUSE", "package": repos.BASE_PACKAGES[base],
         "dir": "/usr/share/zypp/local/service/openSUSE",
         "seed": oss_url(base)},
        {"name": "nazoos", "package": "nazoos-repos",
         "dir": "/usr/share/zypp/local/service/nazoos",
         "seed": ("https://download.opensuse.org"
                  + channel_repo_paths(base)["beta"])},
    ]


# Packages Packman rebuilds with full codecs. A mix of Packman and openSUSE
# builds of these breaks video playback after an update. Mesa: Packman
# "Extra" builds openSUSE's Mesa.spec with video codecs (H.264/H.265
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
