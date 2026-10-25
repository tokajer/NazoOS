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

    got = appicons.icon_files(apps, [flathub, swcatalog])

    assert got == {
        "kdenlive": kdenlive.as_uri(),
        "org.gnome.Meld": meld.as_uri(),
        "solaar": solaar.as_uri(),
    }


def test_earlier_dir_wins(tmp_path):
    first = _png(tmp_path / "a" / "x.png")
    _png(tmp_path / "b" / "x.png")
    got = appicons.icon_files([_app("x", [])], [tmp_path / "a", tmp_path / "b"])
    assert got == {"x": first.as_uri()}


def test_missing_caches_give_no_icons(tmp_path):
    assert appicons.icon_files(catalog.APPS, [tmp_path / "none"]) == {}


class _SyncThread:
    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self.run = lambda: target(*args, **(kwargs or {}))

    def start(self):
        self.run()


CMD = ["flatpak", "update", "--appstream", "--noninteractive", "flathub"]


def _patch_fetch(monkeypatch, rc=0):
    """Returns (calls, clock, result): rc calls, fake time, rc to return."""
    calls, clock, result = [], [1000.0], [rc]

    def fake_rc(cmd, timeout=30):
        calls.append((cmd, timeout))
        return result[0]

    monkeypatch.setattr(appicons, "_retry_at", 0.0)
    monkeypatch.setattr(appicons.threading, "Thread", _SyncThread)
    monkeypatch.setattr(appicons.proc, "rc", fake_rc)
    monkeypatch.setattr(appicons.time, "monotonic", lambda: clock[0])
    return calls, clock, result


def test_fetch_flathub_skips_existing_cache(tmp_path, monkeypatch):
    calls, _, _ = _patch_fetch(monkeypatch)
    icons = tmp_path / "128x128"
    icons.mkdir()
    appicons.fetch_flathub(icons)
    assert calls == []


def test_fetch_flathub_runs_once_on_success(tmp_path, monkeypatch):
    calls, _, _ = _patch_fetch(monkeypatch, rc=0)
    appicons.fetch_flathub(tmp_path / "none")
    appicons.fetch_flathub(tmp_path / "none")
    assert calls == [(CMD, 300)]


def test_fetch_flathub_retries_after_failure(tmp_path, monkeypatch):
    calls, clock, _ = _patch_fetch(monkeypatch, rc=1)
    appicons.fetch_flathub(tmp_path / "none")
    appicons.fetch_flathub(tmp_path / "none")
    assert len(calls) == 1
    clock[0] += appicons.RETRY_SECONDS
    appicons.fetch_flathub(tmp_path / "none")
    assert len(calls) == 2


def test_collect_does_not_fetch_on_live_medium(monkeypatch):
    fetched = []
    monkeypatch.setattr(appicons.proc, "is_live", lambda: True)
    monkeypatch.setattr(appicons, "fetch_flathub",
                        lambda *a, **k: fetched.append(1))
    assert appicons.collect([]) == {}
    assert fetched == []
