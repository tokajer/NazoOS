// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.nazoos.common

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
    // Navigation: live = shown on the live medium too. The first page is
    // the fallback for an unknown name. The list must stay constant: the
    // drawer actions are created from it once (actions: ...map(createObject));
    // a re-evaluation would create new Action objects and leak the old ones
    readonly property var pages: [
        { name: "welcome", title: L.tr("Welcome"), icon: "go-home", live: true, file: "WelcomePage.qml" },
        { name: "drivers", title: L.tr("Drivers & codecs"), icon: "preferences-desktop-display", live: false, file: "DriversPage.qml" },
        { name: "gaming", title: L.tr("Gaming & performance"), icon: "input-gaming", live: false, file: "GamingPage.qml" },
        { name: "kernel", title: L.tr("Kernel"), icon: "preferences-system-linux", live: false, file: "KernelPage.qml" },
        { name: "apps", title: L.tr("Apps"), icon: "plasmadiscover", live: false, file: "AppsPage.qml" },
        { name: "drives", title: L.tr("Drives"), icon: "drive-harddisk", live: false, file: "DrivesPage.qml" },
        { name: "system", title: L.tr("System"), icon: "preferences-system", live: false, file: "SystemPage.qml" },
        { name: "repair", title: L.tr("Repair"), icon: "tools-wizard", live: false, file: "RepairPage.qml" },
        { name: "help", title: L.tr("Help"), icon: "help-about", live: true, file: "HelpPage.qml" }
    ]

    // --- helpers used by all pages ---------------------------------------

    function runAction(action, args) {
        backend.run(action, args || [])
    }

    // Actions that may queue the Secure Boot key: ask for the MokManager
    // password first (ADR 0024). "Try again" asks again (mokRetryRequested)
    function askMok(action, args) {
        mokDialog.action = action
        mokDialog.args = args || []
        mokPin.text = mokDialog.suggestion
        mokDialog.open()
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
        const p = pages.find(x => x.name === name) || pages[0]
        name = p.name
        if (name === currentPage) return
        // Drives, services or packages may have changed outside the app
        // since the last action (__main__.py loads it once at start)
        if (currentPage !== "") backend.refreshStale()
        currentPage = name
        pageStack.clear()
        pageStack.push(Qt.resolvedUrl("pages/" + p.file), { app: root })
        if (globalDrawer.modal) globalDrawer.close()
    }

    Component.onCompleted: showPage(startPage)

    // Welcome was started again (nazoos_common/single.py): show its page here
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
        actions: root.pages.map(p => pageAction.createObject(root, { page: p }))
    }

    Component {
        id: pageAction
        Kirigami.Action {
            property var page
            text: page.title
            icon.name: page.icon
            visible: page.live || !root.live
            checkable: true
            checked: root.currentPage === page.name
            onTriggered: root.showPage(page.name)
        }
    }

    Connections {
        target: backend
        function onMokRetryRequested(action, args) {
            root.askMok(action, args)
        }
        function onActionFinished(action, ok, message) {
            if (ok) {
                root.showPassiveNotification(message)
            } else {
                errorDialog.subtitle = message
                errorDialog.canRetry = backend.canRetry
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
        // MokManager runs before Linux with the firmware's keyboard layout
        // (mostly US). Letters and digits only; on a German keyboard only
        // Y and Z differ there, the dialog says what to type (ADR 0024)
        readonly property string suggestion: "nazoos"
        readonly property bool valid: /^[A-Za-z0-9]{4,16}$/.test(mokPin.text)
        // What a German keyboard has to type in MokManager
        readonly property string usLayout: mokPin.text.replace(/[yzYZ]/g,
            c => ({ y: "z", z: "y", Y: "Z", Z: "Y" })[c])
        // Focus only once the dialog is open: before that the popup takes
        // it away again and Enter/Tab reach the window behind it
        onOpened: {
            mokPin.forceActiveFocus()
            mokPin.selectAll()
        }
        title: L.tr("Password for the NazoOS key")
        subtitle: L.tr("After the restart a blue screen (MokManager) asks once for this password to enroll the NazoOS key. Suggested: \"nazoos\". 4 to 16 letters or digits.")
        standardButtons: Kirigami.Dialog.NoButton

        ColumnLayout {
            QQC2.TextField {
                id: mokPin
                Layout.fillWidth: true
                placeholderText: L.tr("Password (4 to 16 letters or digits)")
                validator: RegularExpressionValidator { regularExpression: /[A-Za-z0-9]{0,16}/ }
                onAccepted: if (mokDialog.valid) mokOk.trigger()
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                visible: mokDialog.usLayout !== mokPin.text
                color: Kirigami.Theme.neutralTextColor
                text: L.tr("Z and Y are swapped in the blue screen on a German keyboard: type \"%1\" there.").arg(mokDialog.usLayout)
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
                    mokDialog.close()
                    backend.runMok(mokDialog.action, mokDialog.args, pin)
                }
            },
            Kirigami.Action {
                text: L.tr("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: {
                    mokPin.text = ""
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
                    backend.retry()
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

    LogDialog { id: logDialog }
}
