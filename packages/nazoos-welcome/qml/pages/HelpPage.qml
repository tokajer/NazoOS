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
    title: L.tr("Help")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("Documentation and support") }

        Kirigami.CardsLayout {
            Layout.fillWidth: true
            maximumColumns: 2

            SettingCard {
                iconName: "help-contents"
                title: L.tr("Documentation")
                subtitle: L.tr("Guides for NazoOS: rollback, drivers, gaming.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.openUrl(page.app.repoUrl + "/tree/main/docs")
                }
            }
            SettingCard {
                iconName: "tools-report-bug"
                title: L.tr("Report a problem")
                subtitle: L.tr("Copy the system information below and add it to your report.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.openUrl(page.app.repoUrl + "/issues")
                }
            }
            SettingCard {
                iconName: "applications-games"
                title: "ProtonDB"
                subtitle: L.tr("How well a Windows game runs with Proton, with tips from other players.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.openUrl("https://www.protondb.com")
                }
            }
            SettingCard {
                iconName: "opensuse"
                title: L.tr("openSUSE Tumbleweed")
                subtitle: L.tr("NazoOS is based on Tumbleweed; most of its documentation applies.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.openUrl("https://en.opensuse.org/Portal:Tumbleweed")
                }
            }
        }

        SectionHeader { text: L.tr("System information") }

        QQC2.TextArea {
            id: info
            readOnly: true
            wrapMode: TextEdit.Wrap
            font.family: "monospace"
            text: { page.app.st; return backend.sysinfo() }
            Layout.fillWidth: true
        }
        QQC2.Button {
            text: L.tr("Copy system information")
            icon.name: "edit-copy"
            onClicked: {
                backend.copySysinfo()
                page.app.showPassiveNotification(L.tr("Copied to the clipboard."))
            }
        }

        SectionHeader { text: L.tr("About") }

        QQC2.Label {
            text: L.tr("NazoOS Welcome %1 – free software under the GNU GPL 3.0 or later.").arg(appVersion)
                  + "\n" + L.tr("\"NazoOS\" and the NazoOS logo are trademarks of the NazoOS project.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        RowLayout {
            QQC2.Button {
                text: L.tr("Source code")
                icon.name: "vcs-normal"
                onClicked: page.app.openUrl(page.app.repoUrl)
            }
            QQC2.Button {
                text: L.tr("Disclaimer")
                onClicked: page.app.openUrl(page.app.repoUrl + "/blob/main/DISCLAIMER.md")
            }
            QQC2.Button {
                text: L.tr("Trademark")
                onClicked: page.app.openUrl(page.app.repoUrl + "/blob/main/TRADEMARK.md")
            }
        }
    }
}
