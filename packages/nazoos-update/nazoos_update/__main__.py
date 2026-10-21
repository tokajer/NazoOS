# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: python3 -m nazoos_update [--notify] [--page NAME]"""

import argparse
import sys

from nazoos_common import proc

VERSION = "0.1.0"


def main():
    parser = argparse.ArgumentParser(prog="nazoos-update")
    parser.add_argument("--notify", action="store_true",
                        help="show notifications only (user timer)")
    parser.add_argument("--page", default="update",
                        help="section to show: update or rollback")
    args, qt_args = parser.parse_known_args()

    proc.refuse_root("nazoos-update")

    if args.notify:
        from . import notify
        return notify.main()

    from nazoos_common.qt import QML_DIR, application, find_qml
    from nazoos_common.single import Instance
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtQml import QQmlApplicationEngine

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

    app = application("nazoos-update", "NazoOS Update", "org.nazoos.update",
                      ("system-software-update",), VERSION, qt_args)

    translator = qml_translator()
    backend = Backend()
    backend.refresh()

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("L", translator)
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("startPage", args.page)
    ctx.setContextProperty("instance", instance)
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(
        str(find_qml(__file__, "nazoos-update"))))
    if not engine.rootObjects():
        return 1
    instance.listen()
    rc = app.exec()
    # The engine must go before the translator: QML bindings still call
    # L.tr() while it is torn down ("Cannot call method 'tr' of null")
    del engine
    return rc


if __name__ == "__main__":
    sys.exit(main())
