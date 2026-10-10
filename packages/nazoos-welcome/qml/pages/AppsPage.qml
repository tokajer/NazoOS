// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import "../components"

Kirigami.ScrollablePage {
    id: page
    property var app
    readonly property var st: app.st
    readonly property var categoryNames: ({
        gaming: L.tr("Gaming"), social: L.tr("Chat"),
        media: L.tr("Recording, video and graphics"),
        office: L.tr("Office and tools"), hardware: L.tr("Hardware")
    })
    readonly property var categoryIcons: ({
        gaming: "applications-games", social: "internet-chat",
        media: "applications-multimedia", office: "applications-office",
        hardware: "input-mouse"
    })
    property string filter: ""
    title: L.tr("Apps")

    function matches(a) {
        if (!filter) return true
        const f = filter.toLowerCase()
        return a.name.toLowerCase().includes(f)
               || L.tr(a.summary).toLowerCase().includes(f)
    }

    header: QQC2.ToolBar {
        contentItem: RowLayout {
            Kirigami.SearchField {
                Layout.fillWidth: true
                onTextChanged: page.filter = text
            }
            QQC2.Button {
                visible: page.st.hasDiscover === true
                text: "Discover"
                icon.name: "plasmadiscover"
                onClicked: backend.launch("discover")
            }
            QQC2.Button {
                visible: page.st.hasMyrlyn === true
                text: "Myrlyn"
                icon.name: "system-software-install"
                onClicked: backend.launch("myrlyn")
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            text: L.tr("A selection of popular apps. Flatpaks come from Flathub and run in a sandbox; everything else is in Discover.")
            wrapMode: Text.WordWrap
            opacity: 0.8
            Layout.fillWidth: true
        }

        Repeater {
            model: backend.catalog.categories
            delegate: ColumnLayout {
                id: section
                required property string modelData
                readonly property var apps: backend.catalog.apps.filter(
                    a => a.category === modelData && page.matches(a))
                visible: apps.length > 0
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing

                SectionHeader { text: page.categoryNames[section.modelData] }

                Kirigami.CardsLayout {
                    Layout.fillWidth: true
                    maximumColumns: 2
                    Repeater {
                        model: section.apps
                        delegate: SettingCard {
                            required property var modelData
                            readonly property bool installed:
                                (page.st.apps || {})[modelData.id] === true
                            iconName: modelData.icon
                            fallbackIcon: page.categoryIcons[modelData.category]
                            title: modelData.name
                            subtitle: L.tr(modelData.summary)
                            status: (modelData.kind === "flatpak" ? "Flatpak" : "RPM")
                                    + (installed ? " · " + L.tr("Installed") : "")
                            statusType: installed ? 1 : 0
                            QQC2.Button {
                                enabled: !backend.busy
                                text: installed ? L.tr("Remove") : L.tr("Install")
                                icon.name: installed ? "edit-delete" : "download"
                                onClicked: {
                                    const id = modelData.id
                                    if (installed)
                                        page.app.confirm(
                                            L.tr("Remove %1?").arg(modelData.name),
                                            L.tr("Your settings and files in your home folder are kept."),
                                            L.tr("Remove"),
                                            () => page.app.runAction("app-remove", [id]))
                                    else
                                        page.app.runAction("app-install", [id])
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
