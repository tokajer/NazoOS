# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext translations, exposed to QML as L.tr("English text")."""

import os

from nazoos_common.i18n import translation
from nazoos_common.qt import Translator

DOMAIN = "nazoos-welcome"


def translator(localedir=None):
    """Our texts, then nazoos-update's: "Update now" passes the errors
    of its helper through."""
    localedir = localedir or os.environ.get("NAZOOS_WELCOME_LOCALEDIR")
    return Translator(translation([DOMAIN, "nazoos-update"], localedir))
