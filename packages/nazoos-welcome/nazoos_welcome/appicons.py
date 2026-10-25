# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""App icons for the Apps page before the app is installed.

An app's icon reaches the icon theme only with its package. AppStream
caches already have them: flatpak keeps Flathub's, libzypp writes the
repos' on every refresh (both the source of Discover's pictures). The
file names do not always match the case of the app id
(org.gnome.meld.png, org.kde.kdenlive.desktop.png), so lookup ignores it.
The caches appear only with the first refresh, so the lookup runs with
every state refresh, not once at start.
"""

import math
import threading
import time
from pathlib import Path

from nazoos_common import proc

FLATHUB_APPSTREAM = "/var/lib/flatpak/appstream/flathub"
ICON_DIRS = [
    f"{FLATHUB_APPSTREAM}/x86_64/active/icons/128x128",
    "/var/cache/swcatalog/icons",
]

RETRY_SECONDS = 300

# time.monotonic() before which no new download starts; inf while one runs
_retry_at = 0.0


def _index(dirs):
    """{lowercase id: png path}, earlier dirs win. A dir without PNGs
    directly inside is a swcatalog root: one <repo>/128x128 per repo."""
    found = {}
    for d in map(Path, dirs):
        pngs = list(d.glob("*.png")) or list(d.glob("*/128x128/*.png"))
        for png in pngs:
            key = png.stem.lower().removesuffix(".desktop")
            found.setdefault(key, str(png))
    return found


def icon_files(apps, dirs=ICON_DIRS):
    """{app id: file URL of the cached icon}; apps without one are absent
    (the card then uses the theme icon)."""
    index = _index(dirs)
    result = {}
    for app in apps:
        ids = [app.get("appstream"), app["icon"], *app["refs"]]
        path = next((index[i.lower()] for i in ids
                     if i and i.lower() in index), "")
        if path:
            result[app["id"]] = Path(path).as_uri()
    return result


def _fetch():
    global _retry_at
    rc = proc.rc(["flatpak", "update", "--appstream", "--noninteractive",
                  "flathub"], timeout=300)
    if rc != 0:
        # Offline at the first login (e.g. Wi-Fi not up yet): try again
        # later instead of never. On success the dir exists anyway.
        _retry_at = time.monotonic() + RETRY_SECONDS


def fetch_flathub(path=ICON_DIRS[0]):
    """Download Flathub's AppStream cache in the background if it is missing."""
    global _retry_at
    if Path(path).is_dir() or time.monotonic() < _retry_at:
        return
    _retry_at = math.inf
    # Not waited for: collect() must not wait for a download; the icons
    # appear with the next state refresh (a page change after 30 s).
    threading.Thread(target=_fetch, daemon=True).start()


def collect(apps):
    """Start the Flathub download if needed, return the icons found now."""
    # The live medium would download into its RAM overlay
    if not proc.is_live():
        fetch_flathub()
    return icon_files(apps)
