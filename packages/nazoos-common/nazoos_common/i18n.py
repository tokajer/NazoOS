# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""gettext with fallback domains, no Qt here."""

import gettext


def translation(domains, localedir=None):
    """Translations of DOMAINS[0], then the others for texts it lacks
    (nazoos-welcome shows errors of the nazoos-update helper).
    LOCALEDIR applies to the first domain only (source tree runs)."""
    t = gettext.translation(domains[0], localedir=localedir, fallback=True)
    for domain in domains[1:]:
        t.add_fallback(gettext.translation(domain, fallback=True))
    return t
