# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext translations; the notifier uses _(), QML uses L.tr()."""

import gettext
import os

DOMAIN = "nazoos-update"

_t = gettext.translation(DOMAIN,
                         localedir=os.environ.get("NAZOOS_UPDATE_LOCALEDIR"),
                         fallback=True)


def _(text):
    return _t.gettext(text)


def ngettext(singular, plural, n):
    return _t.ngettext(singular, plural, n)


def qml_translator():
    from PySide6.QtCore import QObject, Slot

    class Translator(QObject):
        @Slot(str, result=str)
        def tr(self, text):
            return _(text)

        @Slot(str, str, int, result=str)
        def trn(self, singular, plural, n):
            return ngettext(singular, plural, n).replace("%1", str(n))

    return Translator()
