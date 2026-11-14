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
            statusType: !page.st.nvidiaDriver ? SettingCard.Neutral : page.st.nvidiaLoaded ? SettingCard.Positive : SettingCard.Neutral
            extraContent: [
                QQC2.ComboBox {
                    id: nvVariant
                    readonly property bool legacyBlocked: currentValue === "legacy"
                        && !!page.st.kernel && page.st.kernel.installed === true
                    visible: !page.st.nvidiaDriver
                    Layout.fillWidth: true
                    textRole: "text"
                    valueRole: "value"
                    currentIndex: page.st.kernel && page.st.kernel.closedGpu ? 1 : 0
                    // A literal index replaces the binding: a state refresh
                    // must not undo the user's choice
                    onActivated: index => currentIndex = index
                    model: [
                        { value: "open", text: L.tr("GeForce GTX 16, RTX 20 and newer (recommended)") },
                        { value: "legacy", text: L.tr("GeForce GTX 750 to GTX 10 series (older cards)") }
                    ]
                },
                QQC2.Label {
                    visible: !page.st.nvidiaDriver && nvVariant.legacyBlocked
                    text: L.tr("The driver for older cards only exists for the openSUSE kernel. On the Kernel page switch back to the openSUSE kernel, restart and remove the NazoOS kernel.")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            ]
            QQC2.Button {
                visible: !page.st.nvidiaDriver
                enabled: !backend.busy && !nvVariant.legacyBlocked
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
            // Only on NVIDIA-only systems: the libva pin is global (system.py)
            visible: page.st.nvidiaOnly === true && !!page.st.nvidiaDriver
            iconName: "video-x-generic"
            title: L.tr("Video acceleration in the browser (optional)")
            subtitle: L.tr("Lets Firefox, Google Chrome and Brave decode web videos on the NVIDIA card instead of the CPU: less CPU load and heat. For this, the sandbox of Firefox's video decoder process is switched off, Chrome and Brave ignore their GPU blocklist, and the add-on driver may stop working after an NVIDIA driver update until it is updated too. Other programs are not affected.")
            status: !page.st.nvidiaVaapi ? ""
                    : page.st.nvidiaVaapiStale ? L.tr("Browser not included yet")
                    : L.tr("Enabled")
            statusType: !page.st.nvidiaVaapi ? SettingCard.Normal
                        : page.st.nvidiaVaapiStale ? SettingCard.Neutral
                        : SettingCard.Positive
            QQC2.Button {
                visible: !page.st.nvidiaVaapi
                enabled: !backend.busy
                text: L.tr("Enable")
                icon.name: "download"
                onClicked: page.app.confirm(
                    L.tr("Enable video acceleration in the browser?"),
                    L.tr("This installs nvidia-vaapi-driver and switches off the sandbox of Firefox's video decoder process (a security trade-off). Firefox settings are changed through a system policy; you can still override them in about:config. Google Chrome and Brave get start options in their menu entries, also for browsers installed later (\"Apply again\").\n\nLog out and in again afterwards."),
                    L.tr("Enable"),
                    () => page.app.runAction("nvidia-vaapi-enable", []))
            }
            QQC2.Button {
                // A Chromium browser installed or updated after enabling
                visible: page.st.nvidiaVaapi === true
                         && page.st.nvidiaVaapiStale === true
                enabled: !backend.busy
                text: L.tr("Apply again")
                icon.name: "view-refresh"
                onClicked: page.app.runAction("nvidia-vaapi-enable", [])
            }
            QQC2.Button {
                visible: page.st.nvidiaVaapi === true
                enabled: !backend.busy
                text: L.tr("Disable")
                icon.name: "edit-delete"
                onClicked: page.app.runAction("nvidia-vaapi-disable", [])
            }
        }

        SettingCard {
            visible: page.st.hasAmd === true
                     || (page.st.gpus || []).some(g => g.vendor === "intel")
            iconName: "preferences-desktop-display"
            title: L.tr("AMD and Intel graphics")
            subtitle: L.tr("The open-source Mesa drivers are already included and kept up to date with the system. Nothing to do.")
            status: L.tr("Ready")
            statusType: SettingCard.Positive
        }

        SettingCard {
            visible: page.st.hasAmd === true
            iconName: "cpu"
            title: L.tr("ROCm for AMD graphics (optional)")
            subtitle: L.tr("Lets programs compute on the graphics card: Blender (HIP), DaVinci Resolve (OpenCL) and local AI tools. Not needed for games. Officially supported are Radeon RX 6000 (RDNA 2) and newer.")
            status: page.st.rocm ? L.tr("Installed") : ""
            statusType: page.st.rocm ? SettingCard.Positive : SettingCard.Normal
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
                    : page.st.packmanRepo === "on" ? L.tr("Packman is enabled, codecs are not installed yet")
                    : page.st.packmanRepo === "off" ? L.tr("Packman is set up but switched off. Install switches it on again.")
                    : L.tr("Not installed")
            statusType: page.st.codecs ? SettingCard.Positive : SettingCard.Normal
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
