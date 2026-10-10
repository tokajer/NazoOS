// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//
// NazoOS kernel opt-in (ADR 0008): stage 1 install next to the openSUSE
// kernel, stage 2 remove the openSUSE kernel after 3 clean starts, way
// back, and the Secure Boot key (MOK).

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
    readonly property var k: st.kernel || {}
    title: L.tr("Kernel")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("NazoOS kernel") }

        SettingCard {
            iconName: "preferences-system-linux"
            fallbackIcon: "cpu"
            title: L.tr("NazoOS gaming kernel")
            subtitle: L.tr("The openSUSE kernel with gaming patches: BORE scheduler for smoother frame times, BBRv3, handheld drivers (Steam Deck, ROG Ally, MSI Claw, Zotac Zone and more), v4l2loopback for virtual cameras. It is installed next to the openSUSE kernel, which stays in the boot menu as a fallback.")
            status: page.k.blocked ? L.tr("Not possible with the closed NVIDIA driver (G06). Switch to the open driver first.")
                    : page.k.running ? L.tr("Running: %1").arg(page.k.release)
                    : page.k.installed ? L.tr("Installed – restart the computer to start it")
                    : ""
            statusType: page.k.blocked ? 3 : page.k.running ? 1 : page.k.installed ? 2 : 0
            QQC2.Button {
                visible: !page.k.installed
                enabled: !backend.busy && !page.k.blocked
                text: L.tr("Install")
                icon.name: "download"
                onClicked: page.app.confirm(
                    L.tr("Install the NazoOS kernel?"),
                    L.tr("The NazoOS kernel becomes the default in the boot menu. The openSUSE kernel stays installed: if something does not work, pick it under \"Advanced options\" in the boot menu.")
                    + (page.k.secureBoot ? "\n\n" + L.tr("Secure Boot is on: after the restart a blue screen (MokManager) asks to enroll the NazoOS key. Choose \"Enroll MOK\", \"Continue\", \"Yes\" and type your administrator (root) password.") : ""),
                    L.tr("Install"),
                    () => page.app.runAction("kernel-install", []))
            }
        }

        SettingCard {
            visible: page.k.running === true && page.k.defaultInstalled === true && !page.k.only
            iconName: "edit-delete"
            title: L.tr("Remove the openSUSE kernel")
            subtitle: L.tr("Once the NazoOS kernel has started cleanly %1 times in a row, the openSUSE kernel can be removed. Updates then never install it again. Older NazoOS kernels and snapshots stay as fallback.").arg(page.k.stableBoots)
            status: L.tr("Clean starts in a row: %1 of %2").arg(Math.min(page.k.boots || 0, page.k.stableBoots)).arg(page.k.stableBoots)
            statusType: (page.k.boots || 0) >= page.k.stableBoots ? 1 : 0
            QQC2.Button {
                enabled: !backend.busy && (page.k.boots || 0) >= page.k.stableBoots
                text: L.tr("Remove")
                icon.name: "edit-delete"
                onClicked: page.app.confirm(
                    L.tr("Remove the openSUSE kernel?"),
                    L.tr("Only the NazoOS kernel stays installed. You can bring the openSUSE kernel back here at any time."),
                    L.tr("Remove"),
                    () => page.app.runAction("kernel-only", []))
            }
        }

        SettingCard {
            visible: page.k.installed === true
            iconName: "edit-undo"
            title: L.tr("Back to the openSUSE kernel")
            subtitle: L.tr("Makes the openSUSE kernel the default again and installs it if it was removed. The NazoOS kernel can then be removed while the openSUSE kernel is running.")
            QQC2.Button {
                visible: page.k.preferred === true || page.k.only === true || page.k.defaultInstalled !== true
                enabled: !backend.busy
                text: L.tr("Use openSUSE kernel")
                onClicked: page.app.runAction("kernel-restore", [])
            }
            QQC2.Button {
                visible: !page.k.running && page.k.defaultInstalled === true
                enabled: !backend.busy
                text: L.tr("Remove NazoOS kernel")
                icon.name: "edit-delete"
                onClicked: page.app.confirm(
                    L.tr("Remove the NazoOS kernel?"),
                    L.tr("The NazoOS kernel and its driver modules are removed. You can install it again later."),
                    L.tr("Remove"),
                    () => page.app.runAction("kernel-remove", []))
            }
        }

        SectionHeader {
            visible: page.k.secureBoot === true && page.k.installed === true
            text: L.tr("Secure Boot")
        }

        SettingCard {
            visible: page.k.secureBoot === true && page.k.installed === true
            iconName: "security-high"
            title: L.tr("NazoOS key (MOK)")
            subtitle: L.tr("With Secure Boot the computer only starts kernels with a trusted key. The NazoOS key is added once in the blue MokManager screen that appears after a restart: \"Enroll MOK\" → \"Continue\" → \"Yes\", then the administrator (root) password. Until then the NazoOS kernel does not start; choose the openSUSE kernel in the boot menu.")
            status: page.k.mok === "enrolled" ? L.tr("Key enrolled")
                    : page.k.mok === "pending" ? L.tr("Waiting for MokManager – restart the computer")
                    : L.tr("Key not enrolled")
            statusType: page.k.mok === "enrolled" ? 1 : page.k.mok === "pending" ? 2 : 3
            QQC2.Button {
                visible: page.k.mok === "missing"
                enabled: !backend.busy
                text: L.tr("Enroll key")
                icon.name: "document-import"
                onClicked: page.app.runAction("mok-import", [])
            }
        }
    }
}
