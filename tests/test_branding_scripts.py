# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos-os-release and activate-theme against a fake root
(NAZOOS_BRANDING_ROOT)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

BRANDING = Path(__file__).parent.parent / "packages/nazoos-branding"
OS_RELEASE = BRANDING / "os-release/nazoos-os-release"
ACTIVATE = BRANDING / "grub2/activate-theme"

if shutil.which("bash") is None or shutil.which("flock") is None:
    pytest.skip("needs bash and flock", allow_module_level=True)

SUSE_OS_RELEASE = """\
NAME="openSUSE Tumbleweed"
# VERSION="20261024"
ID="opensuse-tumbleweed"
ID_LIKE="opensuse suse"
VERSION_ID="20261024"
PRETTY_NAME="openSUSE Tumbleweed"
LOGO="distributor-logo-Tumbleweed"
VARIANT="Old"
VARIANT_ID="old"
"""


def script(path, root, *args):
    return subprocess.run(
        ["bash", str(path), *args], capture_output=True, text=True,
        env={**os.environ, "NAZOOS_BRANDING_ROOT": str(root)})


@pytest.fixture
def root(tmp_path):
    (tmp_path / "usr/lib").mkdir(parents=True)
    (tmp_path / "usr/lib/os-release").write_text(SUSE_OS_RELEASE)
    (tmp_path / "etc/default").mkdir(parents=True)
    (tmp_path / "run").mkdir()
    theme = tmp_path / "usr/share/grub2/themes/nazoos"
    theme.mkdir(parents=True)
    (theme / "theme.txt").write_text("title-text: \"\"\n")
    (theme / "background.jpg").write_bytes(b"jpg")
    (theme / "activate-theme").write_text("#!/bin/bash\n")
    return tmp_path


def test_os_release_is_renamed_and_keeps_the_id(root):
    r = script(OS_RELEASE, root)
    assert r.returncode == 0, r.stderr
    text = (root / "etc/os-release").read_text()
    lines = text.splitlines()
    assert 'NAME="NazoOS"' in lines
    assert 'PRETTY_NAME="NazoOS"' in lines
    assert 'ID="opensuse-tumbleweed"' in lines
    assert 'VERSION_ID="20261024"' in lines
    assert 'VARIANT_ID="nazoos"' in lines
    assert 'VARIANT="Gaming"' in lines
    assert not any(line.startswith(('VARIANT="Old"', 'VARIANT_ID="old"'))
                   for line in lines)
    assert not (root / "etc/os-release").is_symlink()
    assert [p.name for p in (root / "etc").iterdir()
            if p.name.startswith(".os-release")] == []


def test_os_release_restore_makes_the_symlink(root):
    script(OS_RELEASE, root)
    r = script(OS_RELEASE, root, "--restore")
    assert r.returncode == 0, r.stderr
    link = root / "etc/os-release"
    assert link.is_symlink()
    assert os.readlink(link) == "../usr/lib/os-release"
    assert 'NAME="openSUSE Tumbleweed"' in link.read_text()


def test_activate_theme_copies_the_theme_and_sets_the_keys(root):
    default = root / "etc/default/grub"
    default.write_text('GRUB_TIMEOUT=8\n#GRUB_THEME="/old/theme.txt"\n'
                       'GRUB_DISABLE_BOOTNEXT="false"\n')
    r = script(ACTIVATE, root)
    assert r.returncode == 0, r.stderr
    dst = root / "boot/grub2/themes/nazoos"
    assert (dst / "theme.txt").is_file()
    assert (dst / "background.jpg").is_file()
    assert not (dst / "activate-theme").exists()
    lines = default.read_text().splitlines()
    # A commented key is replaced, a missing one is appended; the paths are
    # the ones GRUB sees, not the fake root
    assert lines == ['GRUB_TIMEOUT=8',
                     'GRUB_THEME="/boot/grub2/themes/nazoos/theme.txt"',
                     'GRUB_DISABLE_BOOTNEXT="true"',
                     'GRUB_BACKGROUND="/boot/grub2/themes/nazoos/background.jpg"']


def test_activate_theme_without_grub_defaults_only_copies(root):
    r = script(ACTIVATE, root)
    assert r.returncode == 0, r.stderr
    assert (root / "boot/grub2/themes/nazoos/theme.txt").is_file()
