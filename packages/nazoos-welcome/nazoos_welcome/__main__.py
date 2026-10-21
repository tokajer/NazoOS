# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_welcome [--autostart] [--page NAME]"""

import argparse
import sys

from nazoos_common import proc
from nazoos_common.qt import QML_DIR, application, find_qml
from nazoos_common.single import Instance
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtQml import QQmlApplicationEngine

from . import system
from .backend import Backend
from .i18n import translator as make_translator

VERSION = "0.1.0"


def main():
    parser = argparse.ArgumentParser(prog="nazoos-welcome")
    parser.add_argument("--autostart", action="store_true",
                        help="started at login: quit if disabled or live")
    parser.add_argument("--page", default="",
                        help="page to open (welcome, drivers, gaming, kernel, "
                             "apps, drives, system, repair, help)")
    args, qt_args = parser.parse_known_args()

    proc.refuse_root("nazoos-welcome")

    if args.autostart and (proc.is_live()
                           or not system.autostart_enabled()):
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

    app = application("nazoos-welcome", "NazoOS Welcome",
                      "org.nazoos.welcome",
                      ("nazoos-logo", "start-here"), VERSION, qt_args)

    translator = make_translator()
    backend = Backend(translator)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("L", translator)
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("startPage", args.page or "welcome")
    ctx.setContextProperty("instance", instance)
    ctx.setContextProperty("appVersion", VERSION)
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(
        str(find_qml(__file__, "nazoos-welcome"))))
    if not engine.rootObjects():
        return 1
    instance.listen()
    backend.refresh()
    rc = app.exec()
    # The engine must go before the translator: QML bindings still call
    # L.tr() while it is torn down ("Cannot call method 'tr' of null")
    del engine
    return rc


if __name__ == "__main__":
    sys.exit(main())
