# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Consistency checks between the image, the installer and the packages."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIWI = ROOT / "kiwi/nazoos-image/config.kiwi"
POSTINSTALL = ROOT / "packages/nazoos-calamares-config/scripts/nazoos-postinstall"
DECK_SPEC = ROOT / "packages/nazoos-deck/nazoos-deck.spec"


def test_kernel_cmdline_is_the_same_in_image_and_installer():
    root = ET.parse(KIWI).getroot()
    kiwi = [
        e.attrib["kernelcmdline"]
        for e in root.iter()
        if isinstance(e.tag, str)
        and e.tag.endswith("type")
        and "kernelcmdline" in e.attrib
    ]
    assert len(kiwi) == 2, "expected kernelcmdline on the test and live <type>"
    assert len(set(kiwi)) == 1, f"kernelcmdline differs between profiles in {KIWI}"

    m = re.search(r'GRUB_CMDLINE_LINUX_DEFAULT="([^"]*)"', POSTINSTALL.read_text())
    assert m, "GRUB_CMDLINE_LINUX_DEFAULT not found in nazoos-postinstall"
    assert m.group(1) == kiwi[0], (
        f"update the command line in {POSTINSTALL} and {KIWI} together"
    )


def test_handheld_keep_list_is_in_the_deck_recommends():
    recommends = set(
        re.findall(r"^Recommends:\s*(\S+)", DECK_SPEC.read_text(), re.MULTILINE)
    )
    m = re.search(
        r'^\s*readonly KEEP_ON_DESKTOP="([^"]*)"', POSTINSTALL.read_text(), re.M
    )
    assert m, "KEEP_ON_DESKTOP not found in nazoos-postinstall"
    stale = set(m.group(1).split()) - recommends
    assert not stale, f"KEEP_ON_DESKTOP in {POSTINSTALL} is stale: {sorted(stale)}"


def _kiwi_packages(profile=None):
    """Package names of the <packages type="image"> sections of PROFILE
    (None: the section for every profile)."""
    root = ET.parse(KIWI).getroot()
    return {
        p.attrib["name"]
        for s in root.iter("packages")
        if s.get("type") == "image" and s.get("profiles") == profile
        for p in s.iter("package")
    }


def _built_here():
    """Every binary package name the specs below packages/ build."""
    names = set()
    for spec in ROOT.glob("packages/*/*.spec"):
        text = spec.read_text()
        name = re.search(r"^Name:\s*(\S+)", text, re.M).group(1)
        names.add(name)
        for flag, sub in re.findall(r"^%package\s+(-n\s+)?(\S+)", text, re.M):
            names.add(sub if flag else f"{name}-{sub}")
    return names


def test_image_nazoos_packages_are_built_here():
    listed = {
        n
        for n in _kiwi_packages() | _kiwi_packages("live")
        if n.startswith("nazoos-")
    }
    missing = listed - _built_here()
    assert not missing, f"{KIWI} names packages no spec builds: {sorted(missing)}"


def test_live_only_packages_are_removed_by_the_installer():
    text = POSTINSTALL.read_text()
    m = re.search(r"^for p in ([^;]+); do", text, re.M)
    assert m, "live package loop not found in nazoos-postinstall"
    removed = set(m.group(1).split())
    # Removed elsewhere in the script: the config package itself (last
    # step) and nazoos-deck (desktop installs, device page)
    removed |= {"nazoos-calamares-config", "nazoos-deck"}
    assert re.search(r"^rpm -e nazoos-calamares-config$", text, re.M)
    assert re.search(r"^\s*rpm -e nazoos-deck$", text, re.M)
    live = _kiwi_packages("live")
    assert live, f'no <packages profiles="live"> section in {KIWI}'
    stale = live - removed
    assert not stale, (
        f"live-only packages in {KIWI} stay on installed systems; remove "
        f"them in {POSTINSTALL}: {sorted(stale)}"
    )
