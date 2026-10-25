# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_welcome.appicons: icons from the AppStream caches."""

from nazoos_welcome import appicons, catalog


def _png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _app(icon, refs, **extra):
    return {"id": icon, "icon": icon, "refs": refs, **extra}


def test_finds_flathub_and_repo_icons_ignoring_case(tmp_path):
    flathub, swcatalog = tmp_path / "flathub", tmp_path / "swcatalog"
    kdenlive = _png(flathub / "org.kde.kdenlive.desktop.png")
    meld = _png(swcatalog / "openSUSE_repo-oss" / "128x128" / "org.gnome.meld.png")
    solaar = _png(swcatalog / "openSUSE_repo-oss" / "128x128"
                  / "io.github.pwr_solaar.solaar.png")
    apps = [_app("kdenlive", ["org.kde.kdenlive"]),
            _app("org.gnome.Meld", ["meld"]),
            _app("solaar", ["solaar"], appstream="io.github.pwr_solaar.solaar"),
            _app("printer", ["hplip"])]

    got = appicons.with_icon_files(apps, [flathub, swcatalog])

    assert [a["iconFile"] for a in got] == [
        kdenlive.as_uri(), meld.as_uri(), solaar.as_uri(), ""]
    assert "iconFile" not in apps[0]


def test_earlier_dir_wins(tmp_path):
    first = _png(tmp_path / "a" / "x.png")
    _png(tmp_path / "b" / "x.png")
    got = appicons.with_icon_files([_app("x", [])],
                                   [tmp_path / "a", tmp_path / "b"])
    assert got[0]["iconFile"] == first.as_uri()


def test_missing_caches_keep_the_theme_icon(tmp_path):
    got = appicons.with_icon_files(catalog.APPS, [tmp_path / "none"])
    assert all(a["iconFile"] == "" for a in got)
