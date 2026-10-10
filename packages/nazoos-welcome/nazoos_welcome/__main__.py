# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_welcome [--autostart] [--page NAME]"""

import argparse
import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from . import system
from .backend import Backend
from .i18n import Translator

VERSION = "0.1.0"


def qml_dir():
    for d in (Path(__file__).resolve().parent.parent / "qml",
              Path("/usr/share/nazoos-welcome/qml")):
        if (d / "Main.qml").is_file():
            return d
    sys.exit("nazoos-welcome: Main.qml not found")


def main():
    parser = argparse.ArgumentParser(prog="nazoos-welcome")
    parser.add_argument("--autostart", action="store_true",
                        help="started at login: quit if disabled or live")
    parser.add_argument("--page", default="welcome",
                        help="page to open (welcome, drivers, gaming, kernel, "
                             "apps, drives, system, repair, help)")
    args, qt_args = parser.parse_known_args()

    if args.autostart and (system.is_live()
                           or not system.autostart_enabled()):
        return 0

    # Native Plasma look (qqc2-desktop-style) unless the user chose a style
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")

    # QApplication (not QGuiApplication): the desktop style needs widgets
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("nazoos-welcome")
    app.setApplicationDisplayName("NazoOS Welcome")
    app.setApplicationVersion(VERSION)
    app.setOrganizationDomain("nazoos.org")
    QGuiApplication.setDesktopFileName("org.nazoos.welcome")
    app.setWindowIcon(QIcon.fromTheme("nazoos-logo",
                                      QIcon.fromTheme("start-here")))
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    translator = Translator()
    backend = Backend(translator)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("L", translator)
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("startPage", args.page)
    ctx.setContextProperty("appVersion", VERSION)
    engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        return 1
    backend.refresh()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
