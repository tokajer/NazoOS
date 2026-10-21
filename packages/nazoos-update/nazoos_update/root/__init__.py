# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-update, run by helper/nazoos-update-helper."""

from . import check, snapshots, update

ACTIONS = {"check": check.check, "update": update.update,
           "rollback": snapshots.rollback, "label": snapshots.label}
