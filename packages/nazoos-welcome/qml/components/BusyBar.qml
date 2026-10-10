// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Progress bar at the bottom of every page while the helper runs.
// A page footer (not the window footer): Kirigami's GlobalDrawer would
// overlap a window footer.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.ToolBar {
    property var app
    visible: backend.busy
    position: QQC2.ToolBar.Footer

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing
        QQC2.BusyIndicator {
            running: backend.busy
            Layout.preferredHeight: Kirigami.Units.iconSizes.medium
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
        }
        QQC2.Label {
            text: backend.task + " …"
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        QQC2.Button {
            text: L.tr("Show details")
            icon.name: "view-list-text"
            onClicked: app.showLog()
        }
    }
}
