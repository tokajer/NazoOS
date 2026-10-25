# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""App icons for the Apps page before the app is installed.

An app's icon reaches the icon theme only with its package. AppStream
caches already have them: flatpak keeps Flathub's, libzypp writes the
repos' on every refresh (both the source of Discover's pictures). The
file names do not always match the case of the app id
(org.gnome.meld.png, org.kde.kdenlive.desktop.png), so lookup ignores it.
"""

from pathlib import Path

ICON_DIRS = [
    "/var/lib/flatpak/appstream/flathub/x86_64/active/icons/128x128",
    "/var/cache/swcatalog/icons",
]


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


def with_icon_files(apps, dirs=ICON_DIRS):
    """APPS with "iconFile": file URL of the cached icon, or "" (the card
    then uses the theme icon "icon")."""
    index = _index(dirs)
    result = []
    for app in apps:
        ids = [app.get("appstream"), app["icon"], *app["refs"]]
        path = next((index[i.lower()] for i in ids
                     if i and i.lower() in index), "")
        result.append(dict(app, iconFile=Path(path).as_uri() if path else ""))
    return result
