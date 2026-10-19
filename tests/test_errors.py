# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The "@@error" line between root helper and GUI (ADR 0030)."""

from nazoos_common import errors


def test_round_trip():
    line = errors.encode("'{cmd}' failed (exit code {rc})",
                         {"cmd": "zypper", "rc": 4})
    assert line.startswith(errors.PREFIX)
    text = line[len(errors.PREFIX):]
    assert errors.decode(text) == ("'{cmd}' failed (exit code {rc})",
                                   {"cmd": "zypper", "rc": 4})
    assert errors.message(text) == "'zypper' failed (exit code 4)"


def test_translated_before_filling():
    text = errors.encode("still failing: {units}",
                         {"units": "a.service"})[len(errors.PREFIX):]
    german = {"still failing: {units}": "schlägt weiter fehl: {units}"}
    assert errors.message(text, lambda s: german.get(s, s)) == \
        "schlägt weiter fehl: a.service"


def test_plain_text_from_an_older_helper():
    assert errors.message("unknown user") == "unknown user"
    assert errors.message('["not", "a dict"]') == '["not", "a dict"]'
    assert errors.message('{"msg": 3}') == '{"msg": 3}'


def test_fill_keeps_unknown_fields_and_reaches_no_attributes():
    assert errors.fill("{a} {b}", {"a": 1}) == "1 {b}"
    # str.format would resolve this; fill() leaves it alone
    assert errors.fill("{a.__class__}", {"a": 1}) == "{a.__class__}"


def test_non_ascii_survives():
    text = errors.encode("{x}", {"x": "Größe"})[len(errors.PREFIX):]
    assert errors.message(text) == "Größe"
