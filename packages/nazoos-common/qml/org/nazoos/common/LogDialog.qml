// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

// The action log of the window. Needs the context properties L and backend
// (log, copyLog()) that both apps set, and a Kirigami.ApplicationWindow
// around it: applicationWindow() comes from there
Kirigami.Dialog {
    id: root

    title: L.tr("Details")
    preferredWidth: Kirigami.Units.gridUnit * 40
    standardButtons: Kirigami.Dialog.NoButton
    onOpened: logScroll.toEnd()
    customFooterActions: [
        Kirigami.Action {
            text: L.tr("Copy")
            icon.name: "edit-copy"
            onTriggered: {
                backend.copyLog()
                applicationWindow().showPassiveNotification(L.tr("Copied to the clipboard."))
            }
        },
        Kirigami.Action {
            text: L.tr("Close")
            icon.name: "dialog-close"
            onTriggered: root.close()
        }
    ]

    // Fixed height: otherwise it grows with the text and the dialog
    // scrolls instead, where we cannot follow the end
    LogView {
        id: logScroll
        implicitHeight: Kirigami.Units.gridUnit * 20
        text: backend.log || L.tr("Nothing has run yet.")
    }
}
