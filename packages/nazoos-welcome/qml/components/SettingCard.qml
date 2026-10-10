// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//
// One setting or action: icon, title, explanation, state line, and the
// controls (children) on the right. Extra rows go into "extraContent".

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: card

    property string iconName: ""
    property string fallbackIcon: "application-x-executable"
    property string title: ""
    property string subtitle: ""
    property string status: ""
    // 0 neutral, 1 positive, 2 warning, 3 error
    property int statusType: 0
    default property alias controls: controlRow.data
    property alias extraContent: extraColumn.data

    Layout.fillWidth: true

    contentItem: GridLayout {
        // Controls move below the text when the window is narrow
        columns: card.width > Kirigami.Units.gridUnit * 30 ? 3 : 2
        columnSpacing: Kirigami.Units.largeSpacing
        rowSpacing: Kirigami.Units.smallSpacing

        Kirigami.Icon {
            source: card.iconName
            fallback: card.fallbackIcon
            visible: card.iconName !== ""
            Layout.preferredWidth: Kirigami.Units.iconSizes.large
            Layout.preferredHeight: Kirigami.Units.iconSizes.large
            Layout.alignment: Qt.AlignTop
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Heading {
                level: 3
                text: card.title
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            QQC2.Label {
                text: card.subtitle
                visible: text !== ""
                wrapMode: Text.WordWrap
                opacity: 0.8
                Layout.fillWidth: true
            }
            QQC2.Label {
                text: card.status
                visible: text !== ""
                wrapMode: Text.WordWrap
                font.bold: true
                color: [Kirigami.Theme.textColor,
                        Kirigami.Theme.positiveTextColor,
                        Kirigami.Theme.neutralTextColor,
                        Kirigami.Theme.negativeTextColor][card.statusType]
                Layout.fillWidth: true
            }
            ColumnLayout {
                id: extraColumn
                visible: children.length > 0
                Layout.fillWidth: true
            }
        }

        RowLayout {
            id: controlRow
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.columnSpan: card.width > Kirigami.Units.gridUnit * 30 ? 1 : 2
        }
    }
}
