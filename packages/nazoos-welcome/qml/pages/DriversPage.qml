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
    title: L.tr("Drivers & codecs")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("Graphics") }

        SettingCard {
            iconName: "video-display"
            title: L.tr("Graphics cards in this computer")
            subtitle: (page.st.gpus || []).map(g => g.name).join("\n")
                      || L.tr("No graphics card found.")
        }

        SettingCard {
            visible: page.st.hasNvidia === true
            iconName: "nvidia"
            title: L.tr("NVIDIA driver")
            subtitle: L.tr("Installs NVIDIA's driver from NVIDIA's repository. Needed for good gaming performance on NVIDIA cards.")
            status: !page.st.nvidiaDriver ? L.tr("Not installed")
                    : page.st.nvidiaLoaded ? L.tr("Installed and active")
                    : L.tr("Installed – restart the computer to activate it")
            statusType: !page.st.nvidiaDriver ? 2 : page.st.nvidiaLoaded ? 1 : 2
            extraContent: [
                QQC2.ComboBox {
                    id: nvVariant
                    visible: !page.st.nvidiaDriver
                    Layout.fillWidth: true
                    textRole: "text"
                    valueRole: "value"
                    model: [
                        { value: "open", text: L.tr("GeForce GTX 16, RTX 20 and newer (recommended)") },
                        { value: "legacy", text: L.tr("GeForce GTX 750 to GTX 10 series (older cards)") }
                    ]
                }
            ]
            QQC2.Button {
                visible: !page.st.nvidiaDriver
                enabled: !backend.busy
                text: L.tr("Install")
                icon.name: "download"
                onClicked: {
                    const variant = nvVariant.currentValue
                    page.app.confirm(
                        L.tr("Install the NVIDIA driver?"),
                        L.tr("This adds NVIDIA's repository. NVIDIA's drivers are subject to NVIDIA's own license terms. After the installation, restart the computer.")
                        + (variant === "legacy"
                           ? "\n\n" + L.tr("The driver for older cards is not signed for Secure Boot. If Secure Boot is on, it will not load.")
                           : ""),
                        L.tr("Install"),
                        () => page.app.runAction("nvidia-install", [variant]))
                }
            }
        }

        SettingCard {
            visible: page.st.hasAmd === true
                     || (page.st.gpus || []).some(g => g.vendor === "intel")
            iconName: "preferences-desktop-display"
            title: L.tr("AMD and Intel graphics")
            subtitle: L.tr("The open-source Mesa drivers are already included and kept up to date with the system. Nothing to do.")
            status: L.tr("Ready")
            statusType: 1
        }

        SettingCard {
            visible: page.st.hasAmd === true
            iconName: "cpu"
            title: L.tr("ROCm for AMD graphics (optional)")
            subtitle: L.tr("Lets programs compute on the graphics card: Blender (HIP), DaVinci Resolve (OpenCL) and local AI tools. Not needed for games. Officially supported are Radeon RX 6000 (RDNA 2) and newer.")
            status: page.st.rocm ? L.tr("Installed") : ""
            statusType: page.st.rocm ? 1 : 0
            QQC2.Button {
                visible: !page.st.rocm
                enabled: !backend.busy
                text: L.tr("Install")
                icon.name: "download"
                onClicked: page.app.runAction("rocm-install", [])
            }
            QQC2.Button {
                visible: page.st.rocm === true
                enabled: !backend.busy
                text: L.tr("Remove")
                icon.name: "edit-delete"
                onClicked: page.app.confirm(
                    L.tr("Remove ROCm?"),
                    L.tr("Programs that compute on the graphics card fall back to the CPU. Games are not affected."),
                    L.tr("Remove"),
                    () => page.app.runAction("rocm-remove", []))
            }
        }

        SectionHeader { text: L.tr("Multimedia") }

        SettingCard {
            iconName: "applications-multimedia"
            title: L.tr("Multimedia codecs (Packman)")
            subtitle: L.tr("Full FFmpeg and GStreamer codecs, e.g. for H.264/H.265 videos, streaming and video editing. They come from Packman, a community repository outside of NazoOS and openSUSE.")
            status: page.st.codecs ? L.tr("Installed")
                    : page.st.packmanRepo ? L.tr("Packman is enabled, codecs are not installed yet")
                    : L.tr("Not installed")
            statusType: page.st.codecs ? 1 : 0
            QQC2.Button {
                enabled: !backend.busy
                text: page.st.codecs ? L.tr("Reinstall") : L.tr("Install")
                icon.name: "download"
                onClicked: page.app.confirm(
                    L.tr("Enable Packman codecs?"),
                    L.tr("Packman is run by an independent community, not by NazoOS or openSUSE. Some codecs may be subject to software patents in certain countries. You are responsible for checking whether you may use them where you live.\n\nInstalled multimedia packages will be switched to Packman's versions."),
                    L.tr("Enable"),
                    () => page.app.runAction("codecs-install", []))
            }
        }

        SectionHeader { text: L.tr("Firmware") }

        SettingCard {
            iconName: "cpu"
            title: L.tr("Firmware updates")
            subtitle: L.tr("BIOS/UEFI, SSD and device firmware updates from the vendors (LVFS) appear in Discover together with the other updates.")
            QQC2.Button {
                text: L.tr("Open Discover")
                icon.name: "plasmadiscover"
                onClicked: backend.launch("updates")
            }
        }
    }
}
