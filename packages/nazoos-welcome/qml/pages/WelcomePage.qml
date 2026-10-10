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
    title: L.tr("Welcome")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            spacing: Kirigami.Units.largeSpacing * 2
            Layout.fillWidth: true
            Layout.bottomMargin: Kirigami.Units.largeSpacing

            Kirigami.Icon {
                source: "nazoos-logo"
                fallback: "start-here"
                Layout.preferredWidth: Kirigami.Units.iconSizes.enormous
                Layout.preferredHeight: Kirigami.Units.iconSizes.enormous
            }
            ColumnLayout {
                Layout.fillWidth: true
                Kirigami.Heading {
                    level: 1
                    text: L.tr("Welcome to NazoOS")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    text: page.app.live
                          ? L.tr("You are running NazoOS from the live medium. Try it out, then install it on your computer.")
                          : L.tr("A gaming desktop based on openSUSE Tumbleweed. This app sets up the rest in a few clicks: drivers, codecs, apps and gaming tweaks. Everything that needs administrator rights asks for your password first.")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: Kirigami.MessageType.Information
            text: L.tr("NazoOS is a hobby project, provided \"as is\" without warranty of any kind. Use it at your own risk and keep backups of your data. NazoOS is independent and not affiliated with openSUSE, SUSE or any other company.")
            actions: [
                Kirigami.Action {
                    text: L.tr("Full disclaimer")
                    icon.name: "documentinfo"
                    onTriggered: page.app.openUrl(page.app.repoUrl + "/blob/main/DISCLAIMER.md")
                }
            ]
        }

        SettingCard {
            visible: page.app.live
            iconName: "system-software-install"
            title: L.tr("Install NazoOS")
            subtitle: L.tr("Starts the installer. Your data on other drives stays untouched unless you choose to erase them.")
            QQC2.Button {
                text: L.tr("Install")
                icon.name: "system-software-install"
                onClicked: backend.launch("installer")
            }
        }

        SectionHeader {
            visible: !page.app.live
            text: L.tr("First steps")
        }

        Kirigami.CardsLayout {
            visible: !page.app.live
            Layout.fillWidth: true
            maximumColumns: 2

            SettingCard {
                iconName: "preferences-desktop-display"
                title: L.tr("1. Drivers & codecs")
                subtitle: L.tr("NVIDIA driver and multimedia codecs for videos and streaming.")
                status: page.app.st.hasNvidia && !page.app.st.nvidiaDriver
                        ? L.tr("NVIDIA graphics card without driver")
                        : ""
                statusType: 2
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.showPage("drivers")
                }
            }
            SettingCard {
                iconName: "input-gaming"
                title: L.tr("2. Gaming & performance")
                subtitle: L.tr("CPU scheduler, GPU overclocking, handheld mode.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.showPage("gaming")
                }
            }
            SettingCard {
                iconName: "plasmadiscover"
                title: L.tr("3. Apps")
                subtitle: L.tr("Discord, OBS Studio, Heroic, ProtonUp-Qt and more with one click.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.showPage("apps")
                }
            }
            SettingCard {
                iconName: "drive-harddisk"
                title: L.tr("4. Drives")
                subtitle: L.tr("Mount extra drives automatically, e.g. for a Steam library.")
                QQC2.Button {
                    text: L.tr("Open")
                    onClicked: page.app.showPage("drives")
                }
            }
        }

        SettingCard {
            visible: !page.app.live
            iconName: "system-reboot"
            title: L.tr("Something broke after an update?")
            subtitle: L.tr("NazoOS takes a snapshot before every update. Restart, choose \"Start bootloader from a read-only snapshot\" in the boot menu and pick the last working state.")
            QQC2.Button {
                text: L.tr("Learn more")
                onClicked: page.app.showPage("system")
            }
        }

        QQC2.Switch {
            visible: !page.app.live
            text: L.tr("Show this window at login")
            checked: page.app.st.autostart !== false
            onToggled: backend.setAutostart(checked)
            Layout.topMargin: Kirigami.Units.largeSpacing
        }
    }
}
