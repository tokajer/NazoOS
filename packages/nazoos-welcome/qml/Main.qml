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

    // Actions that may queue the Secure Boot key: ask for the MokManager
    // password first (ADR 0024). "Try again" asks again, it is not kept
    function askMok(action, args) {
        mokDialog.action = action
        mokDialog.args = args || []
        mokPin.text = ""
        mokPin2.text = ""
        mokDialog.open()
        mokPin.forceActiveFocus()
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

    // Welcome was started again (single.py): show its page here
    Connections {
        target: instance
        function onPageRequested(name) {
            if (name) root.showPage(name)
            if (root.visibility === Window.Minimized) root.showNormal()
            root.raise()
            root.requestActivate()
        }
    }

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
        id: mokDialog
        property string action: ""
        property var args: []
        // Digits only: MokManager runs before Linux with the firmware's
        // keyboard layout (mostly US), letters like y/z can end up swapped
        readonly property bool valid: /^[0-9]{4,16}$/.test(mokPin.text)
                                      && mokPin.text === mokPin2.text
        title: L.tr("Number for the NazoOS key")
        subtitle: L.tr("After the restart a blue screen (MokManager) asks you once to confirm the NazoOS key. Choose a number with 4 to 16 digits now and type it there. Only digits, because that screen may use a different keyboard layout.")
        standardButtons: Kirigami.Dialog.NoButton

        ColumnLayout {
            QQC2.TextField {
                id: mokPin
                Layout.fillWidth: true
                placeholderText: L.tr("Number (4 to 16 digits)")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhDigitsOnly
                validator: RegularExpressionValidator { regularExpression: /[0-9]{0,16}/ }
                onAccepted: mokPin2.forceActiveFocus()
            }
            QQC2.TextField {
                id: mokPin2
                Layout.fillWidth: true
                placeholderText: L.tr("Repeat the number")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhDigitsOnly
                validator: RegularExpressionValidator { regularExpression: /[0-9]{0,16}/ }
                onAccepted: if (mokDialog.valid) mokOk.trigger()
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                visible: mokPin2.text.length > 0 && mokPin.text !== mokPin2.text
                color: Kirigami.Theme.negativeTextColor
                text: L.tr("The numbers do not match.")
            }
        }

        customFooterActions: [
            Kirigami.Action {
                id: mokOk
                text: L.tr("Continue")
                icon.name: "dialog-ok"
                enabled: mokDialog.valid
                onTriggered: {
                    const pin = mokPin.text
                    mokPin.text = ""
                    mokPin2.text = ""
                    mokDialog.close()
                    root.lastRun = [mokDialog.action, mokDialog.args, true]
                    backend.runMok(mokDialog.action, mokDialog.args, pin)
                }
            },
            Kirigami.Action {
                text: L.tr("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: {
                    mokPin.text = ""
                    mokPin2.text = ""
                    mokDialog.close()
                }
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
                    if (root.lastRun[2])
                        root.askMok(root.lastRun[0], root.lastRun[1])
                    else
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
        standardButtons: Kirigami.Dialog.NoButton
        onOpened: logScroll.toEnd()
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
        // Fixed size: Kirigami.Dialog sizes itself after the content's
        // implicit height, so a view as tall as the text grew the dialog
        // with every line (binding loop on y, high CPU) and only the
        // dialog's own outer view could scroll
        QQC2.ScrollView {
            id: logScroll
            implicitWidth: Kirigami.Units.gridUnit * 40
            implicitHeight: Kirigami.Units.gridUnit * 22

            // Follow new output like a terminal. A read-only TextArea
            // without focus does not scroll the view to its cursor
            function toEnd() {
                const f = contentItem
                f.contentY = Math.max(0, f.contentHeight - f.height)
            }

            QQC2.TextArea {
                id: logArea
                readOnly: true
                wrapMode: TextEdit.Wrap
                font.family: "monospace"
                text: backend.log || L.tr("Nothing has run yet.")
                onTextChanged: Qt.callLater(logScroll.toEnd)
            }
        }
    }
}
