# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_update [--notify] [--page NAME]"""

import argparse
import os
import signal
import sys
from pathlib import Path

VERSION = "0.1.0"


def qml_dir():
    for d in (Path(__file__).resolve().parent.parent / "qml",
              Path("/usr/share/nazoos-update/qml")):
        if (d / "Main.qml").is_file():
            return d
    sys.exit("nazoos-update: Main.qml not found")


def main():
    parser = argparse.ArgumentParser(prog="nazoos-update")
    parser.add_argument("--notify", action="store_true",
                        help="show notifications only (user timer)")
    parser.add_argument("--page", default="update",
                        help="section to show: update or rollback")
    args, qt_args = parser.parse_known_args()

    if args.notify:
        from . import notify
        return notify.main()

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication

    from .backend import Backend
    from .i18n import qml_translator

    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("nazoos-update")
    app.setApplicationDisplayName("NazoOS Update")
    app.setApplicationVersion(VERSION)
    app.setOrganizationDomain("nazoos.org")
    QGuiApplication.setDesktopFileName("org.nazoos.update")
    app.setWindowIcon(QIcon.fromTheme("system-software-update"))
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    translator = qml_translator()
    backend = Backend()
    backend.refresh()

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("L", translator)
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("startPage", args.page)
    engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
