# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_update [--notify | --notify-one KEY] [--page NAME]"""

import argparse
import sys

from nazoos_common import proc

VERSION = "0.1.0"


def main():
    parser = argparse.ArgumentParser(prog="nazoos-update")
    parser.add_argument("--notify", action="store_true",
                        help="show notifications only (user timer)")
    parser.add_argument("--notify-one", metavar="KEY",
                        help="show one notification and wait for its "
                        "button (own unit)")
    parser.add_argument("--page", default="update",
                        help="section to show: update or rollback")
    args, qt_args = parser.parse_known_args()

    proc.refuse_root("nazoos-update")

    if args.notify:
        from . import notify
        return notify.main()
    if args.notify_one:
        from . import notify
        return notify.notify_one(args.notify_one)

    from nazoos_common.qt import application, run_qml
    from nazoos_common.single import Instance
    from PySide6.QtCore import QCoreApplication

    from .backend import Backend
    from .i18n import qml_translator

    # Already open (KRunner, menu or a notification button started it
    # again): show the page there instead of a second window
    instance = Instance("nazoos-update")
    if not instance.acquire():
        # QLocalSocket needs an application object, not a window
        _app = QCoreApplication(sys.argv[:1])
        instance.send(args.page)
        return 0

    # Kept alive: the application dies with its last reference
    _app = application("nazoos-update", "NazoOS Update", "org.nazoos.update",
                       ("system-software-update",), VERSION, qt_args)

    translator = qml_translator()
    backend = Backend()

    return run_qml(__file__, "nazoos-update", instance,
                   {"L": translator, "backend": backend,
                    "startPage": args.page})


if __name__ == "__main__":
    sys.exit(main())
