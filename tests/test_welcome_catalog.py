# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_welcome.catalog: parsers and the action list."""

import pytest

from nazoos_welcome import catalog
from nazoos_welcome.root import ACTIONS


@pytest.mark.parametrize("value, expected", [
    ("045e:028e:1", {"045e:028e": 1}),
    (" 045E:028E:2 ", {"045e:028e": 2}),
    ("045e:028e:1,054c:09cc:4", {"045e:028e": 1, "054c:09cc": 4}),
    ("", {}),
    # dropped: bad hex, short id, interval 0, not a number, missing part
    ("xyz1:028e:1,45e:028e:1,045e:028e:0,045e:028e:x,045e:028e", {}),
    ("045e:028e:1,,junk", {"045e:028e": 1}),
])
def test_pollrate_parse(value, expected):
    assert catalog.pollrate_parse(value) == expected


def test_pollrate_format_round_trip():
    overrides = {"054c:09cc": 4, "045e:028e": 1}
    text = catalog.pollrate_format(overrides)
    assert text == "045e:028e:1,054c:09cc:4"   # sorted: stable cmdline
    assert catalog.pollrate_parse(text) == overrides


def test_every_action_has_a_label_and_the_other_way_round():
    assert set(ACTIONS) == set(catalog.ACTION_LABELS)


def test_every_app_category_is_shown_or_hidden_on_purpose():
    shown = set(catalog.APP_CATEGORIES)
    assert not shown & catalog.HIDDEN_CATEGORIES
    for a in catalog.APPS:
        assert a["category"] in shown | catalog.HIDDEN_CATEGORIES, a["id"]
