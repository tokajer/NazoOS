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

    footer: BusyBar { app: page.app }
    readonly property var st: app.st
    title: L.tr("System")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("Updates") }

        SettingCard {
            visible: page.st.hasNazoosUpdate === true || page.st.hasDiscover === true
            iconName: "system-software-update"
            title: L.tr("Update the system")
            subtitle: L.tr("Installs all system and Flatpak updates. A snapshot is taken before, so you can go back if something breaks.")
            QQC2.Button {
                visible: page.st.hasNazoosUpdate === true
                enabled: !backend.busy
                text: L.tr("Update now")
                icon.name: "system-software-update"
                onClicked: page.app.confirm(
                    L.tr("Update the system now?"),
                    L.tr("This can take a while. Keep the computer on and connected until it is done, then restart it."),
                    L.tr("Update"),
                    () => page.app.runAction("system-update", []))
            }
            QQC2.Button {
                visible: page.st.hasNazoosUpdate === true || page.st.hasDiscover === true
                text: page.st.hasNazoosUpdate ? "NazoOS Update" : "Discover"
                onClicked: backend.launch(page.st.hasNazoosUpdate ? "nazoos-update" : "updates")
            }
        }

        SettingCard {
            id: channelCard
            // Hidden in the live session and without nazoos-repos
            visible: !page.st.live && (page.st.channel || "") !== ""
            readonly property bool beta: page.st.channel === "beta"
            iconName: "server-database"
            title: L.tr("Update channel")
            subtitle: L.tr("Stable gets NazoOS updates after they were tested. Beta gets them right away: newest changes, but things can break. Tumbleweed and the NazoOS kernel are the same in both.")
            status: beta ? L.tr("Beta (test versions)") : L.tr("Stable")
            statusType: beta ? SettingCard.Neutral : SettingCard.Positive
            QQC2.Button {
                enabled: !backend.busy
                text: channelCard.beta ? L.tr("Switch to Stable") : L.tr("Switch to Beta")
                onClicked: {
                    const toBeta = !channelCard.beta
                    page.app.confirm(
                        toBeta ? L.tr("Switch to the beta channel?") : L.tr("Switch to the stable channel?"),
                        toBeta ? L.tr("NazoOS packages are replaced by their newest, untested versions. A snapshot is taken first, so you can go back. Report problems on GitHub.")
                               : L.tr("NazoOS packages go back to the tested versions; some can become older. A snapshot is taken first."),
                        L.tr("Switch"),
                        () => page.app.runAction("channel", [toBeta ? "beta" : "stable"]))
                }
            }
        }

        SectionHeader { text: L.tr("Snapshots and rollback") }

        SettingCard {
            iconName: "document-revert"
            title: L.tr("Snapshots")
            subtitle: L.tr("If the system does not start or misbehaves after an update: restart, choose \"Start bootloader from a read-only snapshot\" in the boot menu and pick the state before the update. NazoOS Update then offers to make that state permanent.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Create snapshot")
                icon.name: "camera-photo"
                onClicked: page.app.runAction("snapshot", [])
            }
            QQC2.Button {
                visible: page.st.hasBtrfsAssistant === true
                text: "Btrfs Assistant"
                onClicked: backend.launch("btrfs-assistant")
            }
        }

        SectionHeader { text: L.tr("Services") }

        Repeater {
            model: backend.catalog.services
            delegate: SettingCard {
                required property var modelData
                readonly property var sst: (page.st.services || {})[modelData.id] || {}
                iconName: modelData.icon
                fallbackIcon: "system-run"
                title: L.tr(modelData.name)
                subtitle: L.tr(modelData.summary)
                status: !sst.installed ? L.tr("Not installed – switching on installs it")
                        : sst.active ? L.tr("Running")
                        : sst.enabled ? L.tr("Enabled, but not running") : ""
                statusType: sst.active ? SettingCard.Positive : sst.enabled ? SettingCard.Neutral : SettingCard.Normal
                QQC2.Switch {
                    enabled: !backend.busy
                    checked: sst.enabled === true
                    onToggled: {
                        const on = checked
                        checked = Qt.binding(() => sst.enabled === true)
                        backend.setService(modelData.id, on)
                    }
                }
            }
        }

        SectionHeader { text: L.tr("Maintenance") }

        SettingCard {
            iconName: "tools-wizard"
            title: L.tr("Repair")
            subtitle: L.tr("Checks the system for common problems and fixes them. Also: refresh repositories, clean caches, repair Flatpak, bug report.")
            QQC2.Button {
                text: L.tr("Open")
                onClicked: page.app.showPage("repair")
            }
        }
        SettingCard {
            iconName: "preferences-system"
            title: L.tr("System settings")
            subtitle: L.tr("Displays, sound, network, appearance and everything else of the desktop.")
            QQC2.Button {
                text: L.tr("Open")
                onClicked: backend.launch("systemsettings")
            }
        }

        SectionHeader { text: L.tr("Leave NazoOS") }

        SettingCard {
            iconName: "edit-undo"
            title: L.tr("Switch to openSUSE Tumbleweed")
            subtitle: L.tr("Turns this computer into plain openSUSE Tumbleweed without reinstalling. Your files, apps and settings stay.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Switch to Tumbleweed")
                onClicked: page.app.confirm(
                    L.tr("Switch to openSUSE Tumbleweed?"),
                    L.tr("A snapshot is taken first, so you can go back. NazoOS apps and Waydroid are removed, NazoOS Welcome and NazoOS Update disappear. Your other apps and your kernel options stay. If the NazoOS kernel is running, this first moves to the openSUSE kernel: restart and click this button again."),
                    L.tr("Switch"),
                    () => page.app.runAction("tumbleweed-switch", []))
            }
        }
    }
}
