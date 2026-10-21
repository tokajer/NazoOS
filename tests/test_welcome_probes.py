# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parsers of the welcome probes (lspci, lsblk, repo files, rpm -qa)."""

from nazoos_welcome import catalog, repair, system

MARK = catalog.FSTAB_MARKER

LSPCI = """\
00:02.0 "Audio device [0403]" "Intel Corporation [8086]" "Tiger Lake HD Audio [a0c8]"
03:00.0 "VGA compatible controller [0300]" "Advanced Micro Devices, Inc. [AMD/ATI] [1002]" "Navi 31 [Radeon RX 7900 XT/XTX] [744c]" -rc8 "XFX Limited [1eae]" "Device [4351]"
01:00.0 "3D controller [0302]" "NVIDIA Corporation [10de]" "GA107M [GeForce RTX 3050 Mobile] [25a2]" -ra1 "Lenovo [17aa]" "Device [3a4d]"
05:00.0 "Display controller [0380]" "Acme Corp [abcd]" "Gizmo [0001]"
"""


def test_parse_gpus():
    gpus = system.parse_gpus(LSPCI)
    # The audio device is skipped
    assert [g["vendor"] for g in gpus] == ["amd", "nvidia", "other"]
    assert gpus[0]["name"] == ("Advanced Micro Devices, Inc. [AMD/ATI] "
                               "Navi 31 [Radeon RX 7900 XT/XTX]")
    assert gpus[1]["name"] == ("NVIDIA Corporation "
                               "GA107M [GeForce RTX 3050 Mobile]")


def test_parse_gpus_empty():
    assert system.parse_gpus("") == []


def dev(uuid, fstype="ext4", mounts=(), **kw):
    return dict({"path": f"/dev/{uuid}", "uuid": uuid, "fstype": fstype,
                 "label": "", "size": 500_000_000_000, "rm": False,
                 "hotplug": False, "mountpoints": list(mounts)}, **kw)


def test_parse_drives():
    fstab = (f"UUID=rootuuid / btrfs defaults 0 0\n"
             f"UUID=byhand /data ext4 defaults 0 0\n"
             f"{MARK}\nUUID=ours /mnt/Games ext4 nofail 0 0\n")
    devs = [
        dev("rootuuid", "btrfs", ["/"]),
        dev("usbstick", rm=True),
        dev("vfat1", "vfat"),
        dev("byhand"),
        dev("ours", mounts=["/mnt/Games"]),
        dev("media1", "exfat", ["/run/media/me/media1"], label="Data"),
        dev("elsewhere", mounts=["/srv/x"]),
        dev("idle", "ntfs"),
    ]
    result = system.parse_drives(devs, fstab, "rootuuid")
    assert [d["uuid"] for d in result] == ["ours", "media1", "idle"]
    ours, auto, idle = result
    assert ours["managed"] and ours["mountpoint"] == "/mnt/Games"
    assert not auto["managed"] and auto["label"] == "Data"
    assert idle["mountpoint"] == "" and idle["size"] == "500.0 GB"


STANDARD = [(r["url"], True) for r in catalog.STANDARD_REPOS]
NAZOOS = ("https://download.opensuse.org" + catalog.NAZOOS_REPO_PATHS[1],
          True)
SERVICES = {s["name"]: True for s in catalog.REPO_SERVICES}


def test_repo_problems_all_fine():
    assert repair.repo_problems(STANDARD + [NAZOOS], SERVICES) == []


def test_repo_problems_disabled_standard_repo():
    repos = [(url, enabled and "update" not in url)
             for url, enabled in STANDARD]
    assert repair.repo_problems(repos + [NAZOOS], SERVICES) == ["repo-update"]


def test_repo_problems_missing_service():
    services = dict(SERVICES, openSUSE=False)
    assert repair.repo_problems(STANDARD + [NAZOOS], services) == ["openSUSE"]
    # No service "nazoos" at all: reported once, not twice
    services = {"openSUSE": True}
    assert repair.repo_problems(STANDARD, services) == ["nazoos"]


def test_repo_problems_nazoos_repo_missing():
    assert repair.repo_problems(STANDARD, SERVICES) == ["nazoos"]


def test_mixed_packman():
    text = ("ffmpeg-7\thttp://packman.links2linux.de\n"
            "libavcodec61\topenSUSE\n"
            "Mesa\topenSUSE\n"
            "bash\topenSUSE\n")
    assert repair.mixed_packman(text) == ["Mesa", "libavcodec61"]


def test_mixed_packman_32bit_kept_at_opensuse():
    text = ("libavcodec62\thttp://packman.links2linux.de\n"
            "libavcodec62-32bit\topenSUSE\n"
            "Mesa-32bit\topenSUSE\n")
    assert repair.mixed_packman(text) == []
    text += "libavutil60-32bit\thttp://packman.links2linux.de\n"
    assert repair.mixed_packman(text) == ["Mesa-32bit", "libavcodec62-32bit"]


def test_mixed_packman_without_packman_builds():
    assert repair.mixed_packman("ffmpeg-7\topenSUSE\nMesa\topenSUSE\n") == []


def test_deck_in_repos_caches_only_success(monkeypatch):
    codes = iter([7, 0])
    calls = []

    def fake_rc(cmd, timeout=30):
        calls.append(cmd)
        return next(codes)

    monkeypatch.setattr(system, "_deck_found", False)
    monkeypatch.setattr(system.proc, "rc", fake_rc)
    # First call: zypp lock held, no answer; the next call asks again
    assert system.deck_in_repos() is False
    assert system.deck_in_repos() is True
    assert system.deck_in_repos() is True
    assert len(calls) == 2
