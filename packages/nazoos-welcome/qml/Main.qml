// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    id: root

    title: L.tr("NazoOS Welcome")
    width: Kirigami.Units.gridUnit * 58
    height: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 22

    readonly property var st: backend.state
    readonly property bool live: st.live === true
    readonly property string repoUrl: "https://github.com/tokajer/NazoOS"
    property string currentPage: ""
    property var lastRun: null

    // --- helpers used by all pages ---------------------------------------

    function runAction(action, args) {
        lastRun = [action, args || []]
        backend.run(action, args || [])
    }

    function confirm(title, text, okText, callback) {
        confirmDialog.title = title
        confirmDialog.text = text
        confirmDialog.okText = okText
        confirmDialog.callback = callback
        confirmDialog.open()
    }

    function showLog() {
        logDialog.open()
    }

    function openUrl(url) {
        Qt.openUrlExternally(url)
    }

    function showPage(name) {
        const comps = {
            welcome: welcomePage, drivers: driversPage, gaming: gamingPage,
            kernel: kernelPage, apps: appsPage, drives: drivesPage,
            system: systemPage, repair: repairPage, help: helpPage
        }
        if (!(name in comps)) name = "welcome"
        if (name === currentPage) return
        currentPage = name
        pageStack.clear()
        pageStack.push(comps[name])
        if (globalDrawer.modal) globalDrawer.close()
    }

    Component.onCompleted: showPage(startPage)

    // --- navigation ----------------------------------------------------------

    globalDrawer: Kirigami.GlobalDrawer {
        title: "NazoOS"
        titleIcon: "nazoos-logo"
        modal: !root.wideScreen
        width: Kirigami.Units.gridUnit * 13
        actions: [
            Kirigami.Action {
                text: L.tr("Welcome"); icon.name: "go-home"
                checkable: true; checked: root.currentPage === "welcome"
                onTriggered: root.showPage("welcome")
            },
            Kirigami.Action {
                text: L.tr("Drivers & codecs"); icon.name: "preferences-desktop-display"
                visible: !root.live
                checkable: true; checked: root.currentPage === "drivers"
                onTriggered: root.showPage("drivers")
            },
            Kirigami.Action {
                text: L.tr("Gaming & performance"); icon.name: "input-gaming"
                visible: !root.live
                checkable: true; checked: root.currentPage === "gaming"
                onTriggered: root.showPage("gaming")
            },
            Kirigami.Action {
                text: L.tr("Kernel"); icon.name: "preferences-system-linux"
                visible: !root.live
                checkable: true; checked: root.currentPage === "kernel"
                onTriggered: root.showPage("kernel")
            },
            Kirigami.Action {
                text: L.tr("Apps"); icon.name: "plasmadiscover"
                visible: !root.live
                checkable: true; checked: root.currentPage === "apps"
                onTriggered: root.showPage("apps")
            },
            Kirigami.Action {
                text: L.tr("Drives"); icon.name: "drive-harddisk"
                visible: !root.live
                checkable: true; checked: root.currentPage === "drives"
                onTriggered: root.showPage("drives")
            },
            Kirigami.Action {
                text: L.tr("System"); icon.name: "preferences-system"
                visible: !root.live
                checkable: true; checked: root.currentPage === "system"
                onTriggered: root.showPage("system")
            },
            Kirigami.Action {
                text: L.tr("Repair"); icon.name: "tools-wizard"
                visible: !root.live
                checkable: true; checked: root.currentPage === "repair"
                onTriggered: root.showPage("repair")
            },
            Kirigami.Action {
                text: L.tr("Help"); icon.name: "help-about"
                checkable: true; checked: root.currentPage === "help"
                onTriggered: root.showPage("help")
            }
        ]
    }

    Component { id: welcomePage; WelcomePage { app: root } }
    Component { id: driversPage; DriversPage { app: root } }
    Component { id: gamingPage; GamingPage { app: root } }
    Component { id: kernelPage; KernelPage { app: root } }
    Component { id: appsPage; AppsPage { app: root } }
    Component { id: drivesPage; DrivesPage { app: root } }
    Component { id: systemPage; SystemPage { app: root } }
    Component { id: repairPage; RepairPage { app: root } }
    Component { id: helpPage; HelpPage { app: root } }

    Connections {
        target: backend
        function onActionFinished(action, ok, message) {
            if (ok) {
                root.showPassiveNotification(message)
            } else {
                errorDialog.subtitle = message
                errorDialog.canRetry = root.lastRun !== null
                                      && action !== "launch" && action !== "report"
                errorDialog.open()
            }
        }
    }

    // --- dialogs ----------------------------------------------------------------

    Kirigami.PromptDialog {
        id: confirmDialog
        property string text: ""
        property string okText: ""
        property var callback: null
        subtitle: text
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: confirmDialog.okText || L.tr("Continue")
                icon.name: "dialog-ok"
                onTriggered: {
                    confirmDialog.close()
                    if (confirmDialog.callback) confirmDialog.callback()
                }
            },
            Kirigami.Action {
                text: L.tr("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: confirmDialog.close()
            }
        ]
    }

    Kirigami.PromptDialog {
        id: errorDialog
        property bool canRetry: false
        title: L.tr("That did not work")
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: L.tr("Try again")
                icon.name: "view-refresh"
                visible: errorDialog.canRetry
                onTriggered: {
                    errorDialog.close()
                    root.runAction(root.lastRun[0], root.lastRun[1])
                }
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

    Kirigami.Dialog {
        id: logDialog
        title: L.tr("Details")
        preferredWidth: Kirigami.Units.gridUnit * 40
        preferredHeight: Kirigami.Units.gridUnit * 26
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
                id: logArea
                readOnly: true
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                text: backend.log || L.tr("Nothing has run yet.")
                onTextChanged: cursorPosition = length
            }
        }
    }
}
