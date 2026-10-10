# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext translations, exposed to QML as L.tr("English text")."""

import gettext
import os

from PySide6.QtCore import QObject, Slot

DOMAIN = "nazoos-welcome"


class Translator(QObject):
    def __init__(self, localedir=None):
        super().__init__()
        localedir = localedir or os.environ.get("NAZOOS_WELCOME_LOCALEDIR")
        self._t = gettext.translation(DOMAIN, localedir=localedir,
                                      fallback=True)

    def gettext(self, text):
        return self._t.gettext(text)

    @Slot(str, result=str)
    def tr(self, text):
        return self._t.gettext(text)
