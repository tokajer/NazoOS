# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_welcome [--autostart] [--page NAME]"""

import argparse
import sys

from nazoos_common import proc
from nazoos_common.qt import application, run_qml
from nazoos_common.single import Instance
from PySide6.QtCore import QCoreApplication

from . import autostart
from .backend import Backend
from .i18n import translator as make_translator
from .repair_model import RepairModel

VERSION = "0.1.0"


def main():
    parser = argparse.ArgumentParser(prog="nazoos-welcome")
    parser.add_argument("--autostart", action="store_true",
                        help="started at login: quit if disabled or live")
    parser.add_argument("--page", default="",
                        help="page to open, e.g. kernel or repair "
                             "(qml/Main.qml: pages)")
    args, qt_args = parser.parse_known_args()

    proc.refuse_root("nazoos-welcome")

    if args.autostart and (proc.is_live()
                           or not autostart.enabled()):
        return 0

    # Already open: show the page there. A second autostart (Plasma's
    # session restore already opened the window) changes nothing.
    instance = Instance("nazoos-welcome")
    if not instance.acquire():
        if not args.autostart:
            # QLocalSocket needs an application object, not a window
            _app = QCoreApplication(sys.argv[:1])
            instance.send(args.page)
        return 0

    # Kept alive: the application dies with its last reference
    _app = application("nazoos-welcome", "NazoOS Welcome",
                       "org.nazoos.welcome",
                       ("nazoos-logo", "start-here"), VERSION, qt_args)

    translator = make_translator()
    backend = Backend(translator)
    repair = RepairModel(backend)

    # Only starts a thread: the result arrives through the event loop
    backend.refresh()
    return run_qml(__file__, "nazoos-welcome", instance,
                   {"L": translator, "backend": backend, "repair": repair,
                    "startPage": args.page or "welcome",
                    "appVersion": VERSION})


if __name__ == "__main__":
    sys.exit(main())
