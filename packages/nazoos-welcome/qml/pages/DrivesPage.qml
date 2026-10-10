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
    readonly property var drives: st.drives || []
    title: L.tr("Drives")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            text: L.tr("Internal drives that are not part of the system are only mounted when you open them in Dolphin. Steam needs them mounted at every start for a game library. Here you can mount them automatically under /mnt.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Kirigami.PlaceholderMessage {
            visible: page.drives.length === 0
            icon.name: "drive-harddisk"
            text: L.tr("No additional drives found")
            explanation: L.tr("Only internal drives with ext4, Btrfs, XFS, NTFS or exFAT are shown. USB drives keep working through Dolphin.")
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.gridUnit * 2
        }

        Repeater {
            model: page.drives
            delegate: SettingCard {
                required property var modelData
                iconName: modelData.fstype === "ntfs" ? "drive-harddisk-windows"
                                                      : "drive-harddisk"
                title: (modelData.label || modelData.path) + " (" + modelData.size + ")"
                subtitle: modelData.path + " · " + modelData.fstype
                          + (modelData.fstype === "ntfs"
                             ? "\n" + L.tr("NTFS works, but Proton games can have problems on it. A Linux file system (ext4, Btrfs) is better for a Steam library.")
                             : "")
                status: modelData.managed
                        ? L.tr("Mounted automatically at %1").arg(modelData.mountpoint || "/mnt")
                        : modelData.mountpoint
                          ? L.tr("Mounted only for now at %1").arg(modelData.mountpoint)
                          : L.tr("Not mounted")
                statusType: modelData.managed ? 1 : 0
                QQC2.Button {
                    visible: modelData.managed && modelData.mountpoint !== ""
                    text: L.tr("Open")
                    icon.name: "folder-open"
                    onClicked: page.app.openUrl("file://" + modelData.mountpoint)
                }
                QQC2.Button {
                    enabled: !backend.busy
                    text: modelData.managed ? L.tr("Stop mounting") : L.tr("Mount automatically")
                    icon.name: modelData.managed ? "media-eject" : "media-mount"
                    onClicked: {
                        const uuid = modelData.uuid
                        if (modelData.managed)
                            page.app.runAction("automount-remove", [uuid])
                        else
                            page.app.confirm(
                                L.tr("Mount this drive automatically?"),
                                L.tr("The drive will be mounted at every start under /mnt. A computer still starts if the drive is missing.\n\nNothing on the drive is changed or deleted."),
                                L.tr("Mount automatically"),
                                () => page.app.runAction("automount-add", [uuid]))
                    }
                }
            }
        }
    }
}
