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
    readonly property var pr: st.pollrate || {}
    readonly property var ses: st.session || {}
    title: L.tr("Gaming & performance")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("CPU scheduler") }

        SettingCard {
            iconName: "speedometer"
            title: L.tr("sched_ext scheduler (scx)")
            subtitle: L.tr("Replaces the kernel's CPU scheduler with one tuned for games and desktop latency. Optional: if games stutter or the system behaves oddly, switch it off again.")
            status: page.st.scxActive
                    ? L.tr("Active: %1").arg(page.st.scxScheduler)
                    : page.st.scxEnabled ? L.tr("Enabled, but not running")
                    : L.tr("Off (kernel scheduler)")
            statusType: page.st.scxActive ? SettingCard.Positive : page.st.scxEnabled ? SettingCard.Negative : SettingCard.Normal
            extraContent: [
                RowLayout {
                    QQC2.Label { text: L.tr("Scheduler:") }
                    QQC2.ComboBox {
                        id: schedBox
                        model: backend.catalog.schedulers
                        currentIndex: Math.max(0, model.indexOf(page.st.scxScheduler || "scx_lavd"))
                        onActivated: {
                            if (page.st.scxEnabled)
                                page.app.runAction("scx-enable", [currentText])
                        }
                    }
                    QQC2.Label {
                        text: L.tr("scx_lavd is the default and works well for most games.")
                        opacity: 0.7
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            ]
            QQC2.Switch {
                enabled: !backend.busy
                checked: page.st.scxEnabled === true
                onToggled: {
                    const on = checked
                    // Follow the real state again once the action is done
                    checked = Qt.binding(() => page.st.scxEnabled === true)
                    if (on)
                        page.app.runAction("scx-enable", [schedBox.currentText])
                    else
                        page.app.runAction("scx-disable", [])
                }
            }
        }

        SectionHeader { text: L.tr("Kernel options") }

        Repeater {
            model: backend.catalog.kparams
            delegate: SettingCard {
                required property var modelData
                readonly property var kst: (page.st.kparams || {})[modelData.id] || {}
                visible: kst.shown === true
                iconName: modelData.warning ? "security-low" : "preferences-system-power"
                title: L.tr(modelData.name)
                subtitle: L.tr(modelData.summary)
                status: kst.configured !== kst.active
                        ? L.tr("Restart the computer to apply the change")
                        : kst.active ? L.tr("On") : ""
                statusType: kst.configured !== kst.active ? SettingCard.Neutral : SettingCard.Positive
                QQC2.Switch {
                    enabled: !backend.busy
                    checked: kst.configured === true
                    onToggled: {
                        const id = modelData.id
                        const on = checked
                        checked = Qt.binding(() => kst.configured === true)
                        if (on && modelData.confirm) {
                            page.app.confirm(
                                L.tr(modelData.confirm.title),
                                L.tr(modelData.confirm.text),
                                L.tr(modelData.confirm.ok),
                                () => page.app.runAction("kparam", [id, "on"]))
                        } else {
                            page.app.runAction("kparam", [id, on ? "on" : "off"])
                        }
                    }
                }
            }
        }

        // USB polling rate per device: only kernel-nazoos has the option
        SectionHeader {
            visible: page.pr.available === true
            text: L.tr("Controllers and mice")
        }

        SettingCard {
            visible: page.pr.available === true
            iconName: "input-gamepad"
            title: L.tr("USB polling rate")
            subtitle: L.tr("How often the computer asks a USB controller, mouse or keyboard for input. Many controllers only ask 125 or 250 times per second; 1000 Hz lowers the input lag. The setting is kept after a restart. If a device misbehaves at a higher rate, set it back to \"Device default\".")
            status: (page.pr.devices || []).length === 0
                    ? L.tr("No USB controller, mouse or keyboard is connected.")
                    : L.tr("After a change: unplug the device and plug it in again.")
            statusType: SettingCard.Normal
            extraContent: [
                Repeater {
                    model: page.pr.devices || []
                    delegate: RowLayout {
                        id: devRow
                        required property var modelData
                        readonly property int configured:
                            (page.pr.configured || {})[modelData.id] || 0
                        Layout.fillWidth: true
                        QQC2.Label {
                            text: devRow.modelData.name
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        QQC2.Label {
                            text: !devRow.modelData.connected
                                  ? L.tr("not connected")
                                  : devRow.modelData.hz > 0
                                  ? L.tr("now %1 Hz").arg(devRow.modelData.hz) : ""
                            opacity: 0.7
                        }
                        QQC2.ComboBox {
                            enabled: !backend.busy
                            textRole: "text"
                            model: [
                                { text: L.tr("Device default"), ms: 0 },
                                { text: "125 Hz", ms: 8 },
                                { text: "250 Hz", ms: 4 },
                                { text: "500 Hz", ms: 2 },
                                { text: "1000 Hz", ms: 1 }
                            ]
                            currentIndex: Math.max(0, model.findIndex(o => o.ms === devRow.configured))
                            onActivated: index => {
                                const ms = model[index].ms
                                // Follow the real state again once the action is done
                                currentIndex = Qt.binding(() => Math.max(0, model.findIndex(o => o.ms === devRow.configured)))
                                if (ms !== devRow.configured)
                                    page.app.runAction("pollrate", [devRow.modelData.id, String(ms)])
                            }
                        }
                    }
                }
            ]
        }

        SectionHeader {
            text: L.tr("Gaming mode")
            visible: page.ses.installed === true
        }

        SettingCard {
            visible: page.ses.installed === true
            iconName: "steam"
            title: L.tr("Steam gaming mode")
            subtitle: L.tr("Steam's console interface in Gamescope, like on the Steam Deck. Back to the desktop: Steam menu → Power → Switch to Desktop. Also available as a session on the login screen.")
            status: !page.ses.steam ? L.tr("Install Steam first (Apps page)")
                    : page.ses.bootGaming ? L.tr("Starts in gaming mode (user %1)").arg(page.ses.user)
                    : ""
            statusType: !page.ses.steam ? SettingCard.Neutral : page.ses.bootGaming ? SettingCard.Positive : SettingCard.Normal
            extraContent: [
                RowLayout {
                    QQC2.Switch {
                        id: bootGamingSwitch
                        enabled: !backend.busy && page.ses.steam === true
                        checked: page.ses.bootGaming === true
                        text: L.tr("Start in gaming mode")
                        onToggled: {
                            const on = checked
                            // Follow the real state again once the action is done
                            checked = Qt.binding(() => page.ses.bootGaming === true)
                            page.app.runAction("session-boot-mode", [on ? "gaming" : "desktop"])
                        }
                    }
                    QQC2.Label {
                        text: L.tr("Logs you in automatically and starts Steam, like a console. The desktop is then used for one session only.")
                        opacity: 0.7
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            ]
            QQC2.Button {
                enabled: page.ses.steam === true
                text: L.tr("Switch now")
                icon.name: "go-next"
                onClicked: page.app.confirm(
                    L.tr("Switch to gaming mode?"),
                    L.tr("This ends the desktop session. Save your work first. Steam starts in gaming mode; \"Switch to Desktop\" in Steam's power menu brings you back."),
                    L.tr("Switch to gaming mode"),
                    () => backend.launch("gaming-mode"))
            }
        }

        SectionHeader { text: L.tr("Handheld") }

        SettingCard {
            iconName: "input-gamepad"
            title: L.tr("Steam Deck and handheld support")
            subtitle: L.tr("Gamescope session with Steam's gaming mode, controller and fan support for Steam Deck, Legion Go, ROG Ally and similar devices.")
            status: page.st.deckInstalled ? L.tr("Installed")
                    : !page.st.deckAvailable ? L.tr("Not available yet")
                    : page.ses.handheld ? L.tr("Recommended: %1 detected").arg(page.ses.handheld)
                    : ""
            statusType: page.st.deckInstalled ? SettingCard.Positive : page.ses.handheld ? SettingCard.Neutral : SettingCard.Normal
            QQC2.Button {
                visible: !page.st.deckInstalled
                enabled: !backend.busy && page.st.deckAvailable === true
                text: L.tr("Install")
                icon.name: "download"
                onClicked: page.app.runAction("deck-install", [])
            }
        }

        // Opt-in: jupiter-dock-updater-bin downloads Valve's proprietary
        // updater; Steam uses it when the dock is connected
        SettingCard {
            id: dockCard
            readonly property bool installed: (page.st.apps || {}).deckdock === true
            visible: (page.ses.handheld || "").startsWith("Steam Deck")
            iconName: "preferences-desktop-peripherals"
            title: L.tr("Steam Deck dock firmware")
            subtitle: L.tr("Lets Steam update the firmware of the official Steam Deck dock. Downloads Valve's updater (proprietary) during installation.")
            status: installed ? L.tr("Installed") : ""
            statusType: installed ? SettingCard.Positive : SettingCard.Normal
            QQC2.Button {
                enabled: !backend.busy
                text: dockCard.installed ? L.tr("Remove") : L.tr("Install")
                icon.name: dockCard.installed ? "edit-delete" : "download"
                onClicked: page.app.runAction(dockCard.installed ? "app-remove" : "app-install",
                                              ["deckdock"])
            }
        }

        SectionHeader { text: L.tr("Tools") }

        SettingCard {
            iconName: "preferences-system-performance"
            title: L.tr("GPU and cooling")
            subtitle: L.tr("LACT: GPU clocks, power limit and fan curve. CoolerControl: fans and pumps of the whole system.")
            QQC2.Button {
                visible: page.st.hasLact === true
                text: "LACT"
                onClicked: backend.launch("lact")
            }
            QQC2.Button {
                visible: page.st.hasCoolerControl === true
                text: "CoolerControl"
                onClicked: backend.launch("coolercontrol")
            }
        }

        SettingCard {
            iconName: "steam"
            title: L.tr("Steam launch options")
            subtitle: L.tr("In Steam, right-click a game → Properties → Launch options:")
            extraContent: [
                QQC2.TextField {
                    readOnly: true
                    text: "gamemoderun mangohud %command%"
                    font.family: "monospace"
                    Layout.fillWidth: true
                },
                QQC2.Label {
                    text: L.tr("GameMode raises the game's priority while it runs; MangoHud shows FPS and frame times (toggle with Shift+F12).")
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    Layout.fillWidth: true
                }
            ]
        }
    }
}
