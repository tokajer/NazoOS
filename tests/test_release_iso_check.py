# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decisions of .github/scripts/release-iso-check.py (ADR 0025)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parent.parent
          / ".github/scripts/release-iso-check.py")
spec = importlib.util.spec_from_file_location("release_iso_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

PKG = "0.1.0+git20261022.1792699431.d2bd1a6-86.1"


@pytest.fixture
def state():
    """Frozen ISO with current packages, mirrors have its snapshot."""
    return {"code": "disabled", "dirty": False,
            "iso": "NazoOS.x86_64-0.1.0-release-Build7.2.iso",
            "sha": "new", "published": "old",
            "image_tw": "20261023-4366.1", "mirror": "20261023",
            "image_pkgs": {"nazoos-welcome": PKG},
            "released": {"nazoos-welcome": PKG, "nazoos-binder": "1-1.1"}}


def test_frozen_iso_is_published_when_the_mirrors_have_its_snapshot(state):
    assert check.decide(state)[:2] == ("keep", True)


def test_frozen_iso_newer_than_the_mirrors_waits(state):
    state["mirror"] = "20261022"
    assert check.decide(state)[:2] == ("keep", False)


def test_finished_build_is_frozen_and_waits_for_the_mirrors(state):
    # The race of 2026-10-24: built against a snapshot the mirrors lack
    state.update(code="succeeded", mirror="20261022")
    assert check.decide(state)[:2] == ("disable", False)


def test_finished_build_is_frozen_and_published(state):
    state["code"] = "succeeded"
    assert check.decide(state)[:2] == ("disable", True)


@pytest.mark.parametrize("code", ["building", "scheduled", "blocked"])
def test_running_build_is_left_alone(state, code):
    state["code"] = code
    assert check.decide(state)[:2] == ("keep", False)


def test_dirty_result_is_left_alone(state):
    state.update(code="succeeded", dirty=True)
    assert check.decide(state)[:2] == ("keep", False)


def test_failed_build_publishes_nothing(state):
    state["code"] = "failed"
    assert check.decide(state)[:2] == ("keep", False)


def test_missing_iso_is_built(state):
    state["iso"] = None
    assert check.decide(state)[:2] == ("enable", False)


def test_older_packages_than_release_rebuild(state):
    state["released"]["nazoos-welcome"] = PKG.replace("86.1", "87.1")
    build, publish, reason = check.decide(state)
    assert (build, publish) == ("enable", False)
    assert "nazoos-welcome" in reason


def test_week_old_snapshot_is_refreshed(state):
    state["mirror"] = "20261030"
    assert check.decide(state)[:2] == ("enable", False)


def test_published_iso_stays(state):
    state["published"] = "new"
    assert check.decide(state)[:2] == ("keep", False)


def test_rpm_nvr():
    assert check.rpm_nvr(f"nazoos-branding-plymouth-{PKG}.noarch.rpm") == (
        "nazoos-branding-plymouth", PKG)
    assert check.rpm_nvr(f"nazoos-welcome-{PKG}.src.rpm") is None


def test_days_between_crosses_months():
    assert check.days_between("20261028", "20261104") == 7
