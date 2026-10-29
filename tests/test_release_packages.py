# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The package list of .github/scripts/release-packages.py (release.yml)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "release_packages", ROOT / ".github/scripts/release-packages.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

DEVEL = "home:Tokajer:nazoos:devel"
WORKFLOWS = f"""\
devel_build:
  steps:
    - trigger_services:
        project: {DEVEL}
        package: nazoos-tweaks
    - trigger_services:
        package: nazoos-welcome
        project: {DEVEL}
    - trigger_services:
        project: home:Tokajer:nazoos:kernel
        package: acpi_call
    - trigger_services:
        project: {DEVEL}
        package: nazoos-image
  filters:
    event: push
"""


def test_a_reordered_step_is_found():
    assert rp.packages(WORKFLOWS, DEVEL) == ["nazoos-tweaks", "nazoos-welcome"]


def test_other_projects_are_left_out():
    assert rp.packages(WORKFLOWS, "home:Tokajer:nazoos:kernel") == [
        "acpi_call"]


def test_the_image_is_left_out():
    assert "nazoos-image" not in rp.packages(WORKFLOWS, DEVEL)


def test_the_real_workflow_lists_the_packages():
    found = rp.packages((ROOT / ".obs/workflows.yml").read_text(), DEVEL)
    assert {"nazoos-welcome", "nazoos-common"} <= set(found)
    assert "nazoos-image" not in found
    assert "acpi_call" not in found


def test_every_package_dir_is_built_in_obs():
    # A package missing from .obs/workflows.yml is never rebuilt on push and
    # never released (ADR 0025, 0030)
    text = (ROOT / ".obs/workflows.yml").read_text()
    built = set(rp.packages(text, DEVEL)) | set(
        rp.packages(text, "home:Tokajer:nazoos:kernel"))
    dirs = {d.name for d in (ROOT / "packages").iterdir() if d.is_dir()}
    assert dirs - built == set()


def test_no_package_exits_with_a_message():
    with pytest.raises(SystemExit) as e:
        rp.main(["release-packages.py", "home:Nobody:nothing"])
    assert "no package found" in str(e.value)
