# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_welcome.pollrate: parsing and formatting of the override list."""

import pytest

from nazoos_welcome import pollrate


@pytest.mark.parametrize("value, expected", [
    ("045e:028e:1", {"045e:028e": 1}),
    (" 045E:028E:2 ", {"045e:028e": 2}),
    ("045e:028e:1,054c:09cc:4", {"045e:028e": 1, "054c:09cc": 4}),
    ("", {}),
    # dropped: bad hex, short id, interval 0, not a number, missing part
    ("xyz1:028e:1,45e:028e:1,045e:028e:0,045e:028e:x,045e:028e", {}),
    ("045e:028e:1,,junk", {"045e:028e": 1}),
])
def test_parse(value, expected):
    assert pollrate.parse(value) == expected


def test_format_round_trip():
    overrides = {"054c:09cc": 4, "045e:028e": 1}
    text = pollrate.format_overrides(overrides)
    assert text == "045e:028e:1,054c:09cc:4"   # sorted: stable cmdline
    assert pollrate.parse(text) == overrides
