// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.nazoos.common

Kirigami.ApplicationWindow {
    id: root

    title: L.tr("NazoOS Update")
    width: Kirigami.Units.gridUnit * 40
    height: Kirigami.Units.gridUnit * 34
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 20

    readonly property var st: backend.state
    readonly property bool loaded: st.count !== undefined
    readonly property int count: st.count || 0
    readonly property int snapshot: st.snapshot || 0
    readonly property string error: st.error || ""
    readonly property bool conflict: st.conflict === true
    readonly property bool refreshFailed: st.refresh_failed === true
    readonly property bool keyFailed: st.key_failed === true
    readonly property bool flatpakFailed: st.flatpak_failed === true
    // Date.now() is not a binding dependency: without this the label never ages
    property double now: Date.now()

    // The banner above the pages already explains this failure
    function bannerExplains(action) {
        return ((action === "check" || action === "update") && conflict)
            || (action === "update" && keyFailed)
            || (action === "check" && (refreshFailed || keyFailed))
    }

    function ago(seconds) {
        if (!seconds) return L.tr("never")
        const min = Math.round((root.now / 1000 - seconds) / 60)
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
            id: content
            spacing: Kirigami.Units.largeSpacing

            // --- started from a snapshot: offer rollback --------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.snapshot > 0 && !backend.rolledBack
                type: Kirigami.MessageType.Warning
                text: L.tr("The system was started from snapshot %1. It is read-only: nothing can be installed or changed. If everything works now, make this state permanent.").replace("%1", root.snapshot)
                actions: [
                    Kirigami.Action {
                        text: L.tr("Make permanent")
                        icon.name: "edit-undo"
                        enabled: !backend.busy
                        onTriggered: rollbackDialog.open()
                    }
                ]
            }

            // --- restart after an update or rollback ------------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: backend.rebootNeeded
                type: Kirigami.MessageType.Information
                text: backend.rolledBack
                      ? L.tr("The snapshot was made permanent. Restart the computer to start from it.")
                      : L.tr("Updates were installed. Restart the computer to use them.")
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
                visible: root.refreshFailed
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
                visible: root.keyFailed
                type: Kirigami.MessageType.Warning
                text: L.tr("A package source offers a signing key that is not trusted yet, so it cannot be refreshed:") + "\n"
                      + (root.st.keys || []).map(k => k.shown).join("\n")
                      + "\n" + L.tr("Only trust it if the provider's website shows the same fingerprint. The Repair page of NazoOS Welcome can trust it.")
                actions: [
                    Kirigami.Action {
                        text: L.tr("Open Repair"); icon.name: "tools-wizard"
                        visible: backend.canRepair
                        onTriggered: backend.launch("repair")
                    }
                ]
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.conflict
                type: Kirigami.MessageType.Warning
                text: L.tr("The update needs a decision that cannot be made automatically:") + "\n"
                      + (root.st.problems || []).join("\n")
                      + "\n" + L.tr("In Myrlyn, Updates → Dist-Upgrade shows the conflict and the solutions to choose from.")
                actions: [
                    Kirigami.Action {
                        text: L.tr("Open Myrlyn"); icon.name: "system-software-install"
                        onTriggered: backend.launch("myrlyn")
                    }
                ]
            }

            // --- mirrors still have an older Tumbleweed snapshot -------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.snapshot === 0 && !!root.st.behind
                type: Kirigami.MessageType.Information
                text: L.tr("The download servers do not have the newest Tumbleweed version yet (system: %1, servers: %2). Tumbleweed updates will appear as soon as they have it, usually within a day. NazoOS's own packages can be updated now.")
                      .replace("%1", (root.st.behind || [])[0]).replace("%2", (root.st.behind || [])[1])
            }

            // --- summary ----------------------------------------------------
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                visible: root.loaded && root.snapshot === 0
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: root.error ? "dialog-warning"
                              : root.count > 0 ? "system-software-update"
                              : root.flatpakFailed ? "dialog-warning"
                              : (root.st.checked ? "checkmark" : "view-refresh")
                        Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                        Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Kirigami.Heading {
                            level: 2
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            // the banner above says why; never "up to date" then
                            text: root.conflict ? L.tr("Update on hold")
                                  : root.error ? L.tr("Updates could not be checked")
                                  : root.count > 0
                                  ? L.trn("%1 update available", "%1 updates available", root.count)
                                  : root.flatpakFailed ? L.tr("Flatpak updates could not be checked")
                                  : (root.st.checked ? L.tr("The system is up to date") : L.tr("Not checked yet"))
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            opacity: 0.8
                            text: L.tr("Last check: %1").replace("%1", root.ago(root.st.checked))
                                  + (root.st.update_needs_reboot ? "\n" + L.tr("A restart will be needed afterwards.") : "")
                                  + (root.flatpakFailed && root.count > 0
                                     ? "\n" + L.tr("Flatpak updates could not be checked (no connection to Flathub?).") : "")
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            opacity: 0.8
                            text: L.tr("Before the update a snapshot is taken automatically. If something breaks, pick it in the boot menu under \"Start bootloader from a read-only snapshot\".")
                        }
                        QQC2.CheckBox {
                            Layout.fillWidth: true
                            text: L.tr("Also remove Flatpak runtimes no app needs anymore")
                            checked: backend.cleanFlatpaks
                            enabled: !backend.busy
                            onToggled: backend.cleanFlatpaks = checked
                        }
                    }
                    QQC2.Button {
                        text: L.tr("Update now")
                        icon.name: "system-software-update"
                        highlighted: true
                        enabled: !backend.busy && root.count > 0 && !root.conflict
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
                    id: pkgRow
                    required property var modelData
                    Layout.fillWidth: true
                    // The name wins over the version: git versions are long,
                    // and a cut name ("nazoos-bran…") says nothing
                    QQC2.Label {
                        id: pkgName
                        text: modelData.name
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    QQC2.Label {
                        opacity: 0.7
                        // At most what the full name leaves, but always half
                        // the row; cut from the left so the new version stays
                        Layout.maximumWidth: Math.max(content.width - pkgName.implicitWidth - pkgRow.spacing,
                                                      content.width / 2)
                        elide: Text.ElideLeft
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

    Timer {
        interval: 60000
        running: root.visible
        repeat: true
        onTriggered: root.now = Date.now()
    }

    // Opened from the "Make permanent" notification: ask right away, but
    // only once the window is shown. Opened in Component.onCompleted the
    // dialog has no size yet (binding loop on y) and stays invisible
    Timer {
        interval: 300
        running: startPage === "rollback" && root.visible && root.snapshot > 0
        onTriggered: rollbackDialog.open()
    }

    // Started again (nazoos_common/single.py): show this window instead
    Connections {
        target: instance
        function onPageRequested(name) {
            if (root.visibility === Window.Minimized) root.showNormal()
            root.raise()
            root.requestActivate()
            if (name === "rollback" && root.snapshot > 0 && !backend.busy)
                rollbackDialog.open()
        }
    }

    Connections {
        target: backend
        // A "Done." from the last action must not stay during the next one
        function onBusyChanged() {
            if (backend.busy) root.hidePassiveNotification()
        }
        function onActionFinished(action, ok, message) {
            if (ok) {
                root.showPassiveNotification(message)
            } else if (root.bannerExplains(action)) {
                // The banner has its own button
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
                text: L.tr("Repair")
                icon.name: "tools-wizard"
                visible: backend.canRepair
                onTriggered: { errorDialog.close(); backend.launch("repair") }
            },
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

    LogDialog { id: logDialog }
}
