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
            statusType: page.st.scxActive ? 1 : page.st.scxEnabled ? 3 : 0
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
            model: backend.catalog.kparams.filter(k => k.gpu !== "amd" || page.st.hasAmd)
            delegate: SettingCard {
                required property var modelData
                readonly property var kst: (page.st.kparams || {})[modelData.id] || {}
                iconName: modelData.warning ? "security-low" : "preferences-system-power"
                title: L.tr(modelData.name)
                subtitle: L.tr(modelData.summary)
                status: kst.configured !== kst.active
                        ? L.tr("Restart the computer to apply the change")
                        : kst.active ? L.tr("On") : ""
                statusType: kst.configured !== kst.active ? 2 : 1
                QQC2.Switch {
                    enabled: !backend.busy
                    checked: kst.configured === true
                    onToggled: {
                        const id = modelData.id
                        const on = checked
                        checked = Qt.binding(() => kst.configured === true)
                        if (on && modelData.warning) {
                            page.app.confirm(
                                L.tr("Disable CPU security mitigations?"),
                                L.tr("This removes protection against Spectre, Meltdown and similar CPU attacks. Malicious websites or programs could read data from other programs. Only do this if you know the risk."),
                                L.tr("Disable mitigations"),
                                () => page.app.runAction("kparam", [id, "on"]))
                        } else {
                            page.app.runAction("kparam", [id, on ? "on" : "off"])
                        }
                    }
                }
            }
        }

        SectionHeader { text: L.tr("Handheld") }

        SettingCard {
            iconName: "input-gamepad"
            title: L.tr("Steam Deck and handheld support")
            subtitle: L.tr("Gamescope session with Steam's gaming mode, controller and fan support for Steam Deck, Legion Go, ROG Ally and similar devices.")
            status: page.st.deckInstalled ? L.tr("Installed")
                    : page.st.deckAvailable ? ""
                    : L.tr("Not available yet")
            statusType: page.st.deckInstalled ? 1 : 0
            QQC2.Button {
                visible: !page.st.deckInstalled
                enabled: !backend.busy && page.st.deckAvailable === true
                text: L.tr("Install")
                icon.name: "download"
                onClicked: page.app.runAction("deck-install", [])
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
