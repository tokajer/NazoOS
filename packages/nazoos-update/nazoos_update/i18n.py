# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext translations; the notifier uses _(), QML uses L.tr()."""

import os

from nazoos_common.i18n import translation

DOMAIN = "nazoos-update"

_t = translation([DOMAIN], localedir=os.environ.get("NAZOOS_UPDATE_LOCALEDIR"))


def _(text):
    return _t.gettext(text)


def ngettext(singular, plural, n):
    return _t.ngettext(singular, plural, n)


def qml_translator():
    from nazoos_common.qt import Translator

    return Translator(_t)
