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
            iconName: "system-software-update"
            title: L.tr("Update the system")
            subtitle: L.tr("Installs all system and Flatpak updates. A snapshot is taken before, so you can go back if something breaks.")
            QQC2.Button {
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
                iconName: {
                    const icons = { bluetooth: "preferences-system-bluetooth",
                                    lactd: "preferences-desktop-display",
                                    coolercontrold: "temperature-normal",
                                    sshd: "network-connect",
                                    psd: "internet-web-browser" }
                    return icons[modelData.id] || "system-run"
                }
                title: L.tr(modelData.name)
                subtitle: L.tr(modelData.summary)
                status: !sst.installed ? L.tr("Not installed – switching on installs it")
                        : sst.active ? L.tr("Running")
                        : sst.enabled ? L.tr("Enabled, but not running") : ""
                statusType: sst.active ? 1 : sst.enabled ? 2 : 0
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
            iconName: "view-refresh"
            title: L.tr("Refresh repositories")
            subtitle: L.tr("Reloads the package lists. Helps when Discover or an installation reports outdated or broken repository data.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Refresh")
                onClicked: page.app.runAction("repo-refresh", [])
            }
        }
        SettingCard {
            iconName: "edit-clear-all"
            title: L.tr("Clean package cache")
            subtitle: L.tr("Deletes downloaded package files and cached repository data to free disk space.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Clean")
                onClicked: page.app.runAction("cache-clean", [])
            }
        }
        SettingCard {
            iconName: "flatpak-discover"
            title: L.tr("Flatpak cleanup")
            subtitle: L.tr("Removes runtimes no app needs anymore, or repairs a broken Flatpak installation.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Remove unused")
                onClicked: page.app.runAction("flatpak-unused", [])
            }
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Repair")
                onClicked: page.app.runAction("flatpak-repair", [])
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
    }
}
