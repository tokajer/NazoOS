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
