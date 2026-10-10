// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    title: L.tr("NazoOS Update")
    width: Kirigami.Units.gridUnit * 40
    height: Kirigami.Units.gridUnit * 34
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 20

    readonly property var st: backend.state
    readonly property int count: st.count || 0
    readonly property int snapshot: st.snapshot || 0
    readonly property string error: st.error || ""

    function ago(seconds) {
        if (!seconds) return L.tr("never")
        const min = Math.round((Date.now() / 1000 - seconds) / 60)
        if (min < 2) return L.tr("just now")
        if (min < 120) return L.trn("%1 minute ago", "%1 minutes ago", min)
        const h = Math.round(min / 60)
        if (h < 48) return L.trn("%1 hour ago", "%1 hours ago", h)
        return L.trn("%1 day ago", "%1 days ago", Math.round(h / 24))
    }

    pageStack.initialPage: Kirigami.ScrollablePage {
        id: page
        title: L.tr("Updates")

        actions: [
            Kirigami.Action {
                text: L.tr("Check now")
                icon.name: "view-refresh"
                enabled: !backend.busy && root.snapshot === 0
                onTriggered: backend.run("check")
            },
            Kirigami.Action {
                text: L.tr("Details")
                icon.name: "view-list-text"
                onTriggered: logDialog.open()
            }
        ]

        footer: QQC2.ToolBar {
            visible: backend.busy
            contentItem: RowLayout {
                QQC2.BusyIndicator { running: backend.busy; Layout.preferredHeight: Kirigami.Units.iconSizes.medium }
                QQC2.Label { text: backend.task + " …"; Layout.fillWidth: true; elide: Text.ElideRight }
                QQC2.Button { text: L.tr("Show details"); onClicked: logDialog.open() }
            }
        }

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing

            // --- started from a snapshot: offer rollback --------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.snapshot > 0
                type: Kirigami.MessageType.Warning
                text: L.tr("The system was started from snapshot %1. It is read-only: changes are lost at the next restart. If everything works now, make this state permanent.").replace("%1", root.snapshot)
                actions: [
                    Kirigami.Action {
                        text: L.tr("Make permanent")
                        icon.name: "edit-undo"
                        enabled: !backend.busy
                        onTriggered: rollbackDialog.open()
                    }
                ]
            }

            // --- restart after an update ------------------------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: backend.rebootNeeded
                type: Kirigami.MessageType.Information
                text: L.tr("Updates were installed. Restart the computer to use them.")
                actions: [
                    Kirigami.Action {
                        text: L.tr("Restart now")
                        icon.name: "system-reboot"
                        onTriggered: backend.reboot()
                    }
                ]
            }

            // --- check failed / conflict ------------------------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.error === "refresh"
                type: Kirigami.MessageType.Error
                text: L.tr("The package sources could not be reached. Check the internet connection and try again.")
                actions: [
                    Kirigami.Action {
                        text: L.tr("Try again"); icon.name: "view-refresh"
                        enabled: !backend.busy
                        onTriggered: backend.run("check")
                    }
                ]
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.error === "conflict"
                type: Kirigami.MessageType.Warning
                text: L.tr("The update needs a decision that cannot be made automatically:") + "\n"
                      + (root.st.problems || []).join("\n")
                      + "\n" + L.tr("Myrlyn shows the conflict and offers solutions to choose from.")
                actions: [
                    Kirigami.Action {
                        text: L.tr("Open Myrlyn"); icon.name: "system-software-install"
                        onTriggered: backend.launch("myrlyn")
                    }
                ]
            }

            // --- summary ----------------------------------------------------
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                visible: root.snapshot === 0
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: root.count > 0 ? "system-software-update" : "checkmark"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                        Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Kirigami.Heading {
                            level: 2
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: root.count > 0
                                  ? L.trn("%1 update available", "%1 updates available", root.count)
                                  : (root.st.checked ? L.tr("The system is up to date") : L.tr("Not checked yet"))
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            opacity: 0.8
                            text: L.tr("Last check: %1").replace("%1", root.ago(root.st.checked))
                                  + (root.st.reboot ? "\n" + L.tr("A restart will be needed afterwards.") : "")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            opacity: 0.8
                            text: L.tr("Before the update a snapshot is taken automatically. If something breaks, pick it in the boot menu under \"Start bootloader from a read-only snapshot\".")
                        }
                    }
                    QQC2.Button {
                        text: L.tr("Update now")
                        icon.name: "system-software-update"
                        highlighted: true
                        enabled: !backend.busy && root.count > 0 && root.error !== "conflict"
                        onClicked: backend.run("update")
                    }
                }
            }

            // --- package list -----------------------------------------------
            Kirigami.Heading {
                level: 3
                visible: (root.st.packages || []).length > 0
                text: L.tr("System packages")
            }
            Repeater {
                model: root.snapshot === 0 ? (root.st.packages || []) : []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    QQC2.Label {
                        text: modelData.name
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    QQC2.Label {
                        opacity: 0.7
                        text: {
                            const k = modelData.kind
                            if (k === "install") return L.tr("new") + "  " + modelData.new
                            if (k === "remove") return L.tr("removed")
                            if (modelData.old) return modelData.old + " → " + modelData.new
                            return modelData.new
                        }
                    }
                }
            }
            Kirigami.Heading {
                level: 3
                visible: (root.st.flatpaks || []).length > 0
                text: L.tr("Flatpak apps and runtimes")
            }
            Repeater {
                model: root.snapshot === 0 ? (root.st.flatpaks || []) : []
                delegate: QQC2.Label {
                    required property var modelData
                    text: modelData
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            // --- tools ------------------------------------------------------
            Kirigami.Separator { Layout.fillWidth: true }
            RowLayout {
                QQC2.Button {
                    text: L.tr("Snapshots (Btrfs Assistant)")
                    icon.name: "document-revert"
                    onClicked: backend.launch("btrfs-assistant")
                }
                QQC2.Button {
                    text: L.tr("Packages (Myrlyn)")
                    icon.name: "system-software-install"
                    onClicked: backend.launch("myrlyn")
                }
            }
        }
    }

    Component.onCompleted: {
        if (startPage === "rollback" && snapshot > 0) rollbackDialog.open()
    }

    Connections {
        target: backend
        function onActionFinished(action, ok, message) {
            if (ok) {
                root.showPassiveNotification(message)
            } else {
                errorDialog.subtitle = message
                errorDialog.open()
            }
        }
    }

    Kirigami.PromptDialog {
        id: rollbackDialog
        title: L.tr("Make this state permanent?")
        subtitle: L.tr("The system goes back to snapshot %1 for good. The current, broken state is kept as a snapshot, so this can be undone. Afterwards the computer has to restart.").replace("%1", root.snapshot)
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.tr("Make permanent")
                icon.name: "dialog-ok"
                onTriggered: { rollbackDialog.close(); backend.run("rollback") }
            },
            Kirigami.Action {
                text: L.tr("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: rollbackDialog.close()
            }
        ]
    }

    Kirigami.PromptDialog {
        id: errorDialog
        title: L.tr("That did not work")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.tr("Show details")
                icon.name: "view-list-text"
                onTriggered: { errorDialog.close(); logDialog.open() }
            },
            Kirigami.Action {
                text: L.tr("Close")
                icon.name: "dialog-close"
                onTriggered: errorDialog.close()
            }
        ]
    }

    Kirigami.Dialog {
        id: logDialog
        title: L.tr("Details")
        preferredWidth: Kirigami.Units.gridUnit * 36
        preferredHeight: Kirigami.Units.gridUnit * 24
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.tr("Copy")
                icon.name: "edit-copy"
                onTriggered: {
                    backend.copyLog()
                    root.showPassiveNotification(L.tr("Copied to the clipboard."))
                }
            },
            Kirigami.Action {
                text: L.tr("Close")
                icon.name: "dialog-close"
                onTriggered: logDialog.close()
            }
        ]
        QQC2.ScrollView {
            QQC2.TextArea {
                readOnly: true
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                text: backend.log || L.tr("Nothing has run yet.")
                onTextChanged: cursorPosition = length
            }
        }
    }
}
