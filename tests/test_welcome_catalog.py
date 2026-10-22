# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_welcome.catalog: parsers and the action list."""

from nazoos_welcome import catalog
from nazoos_welcome.root import ACTIONS, apps


def test_every_action_has_a_label_and_the_other_way_round():
    assert set(ACTIONS) == set(catalog.ACTION_LABELS)


def test_every_app_category_is_shown_or_hidden_on_purpose():
    shown = set(catalog.APP_CATEGORIES)
    assert not shown & catalog.HIDDEN_CATEGORIES
    for a in catalog.APPS:
        assert a["category"] in shown | catalog.HIDDEN_CATEGORIES, a["id"]


def test_every_app_setup_step_exists():
    steps = {a["setup"] for a in catalog.APPS if "setup" in a}
    assert "waydroid" in steps
    assert steps <= set(apps.SETUP)
