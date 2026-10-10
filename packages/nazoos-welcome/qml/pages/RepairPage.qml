// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Repair page (ADR 0012): check finds known problems (repair.py), every
// finding has its own fix button; tools and bug report below.

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
    title: L.tr("Repair")

    // Texts per finding id (ids from nazoos_welcome/repair.py)
    readonly property var texts: ({
        rpmdb: { icon: "package-broken", title: L.tr("Package database is damaged"),
                 text: L.tr("The list of installed packages cannot be read. Rebuilding it fixes most cases."),
                 button: L.tr("Rebuild") },
        repos: { icon: "repository", title: L.tr("Standard repositories missing or disabled"),
                 text: L.tr("Without them there are no updates. The missing ones are added again and all are switched on."),
                 button: L.tr("Repair") },
        deps: { icon: "package-broken", title: L.tr("Packages with missing dependencies"),
                text: L.tr("Something these packages need is not installed. The missing parts are installed. If that needs a decision, Myrlyn shows the choices."),
                button: L.tr("Install missing") },
        packman: { icon: "applications-multimedia", title: L.tr("Mixed multimedia packages"),
                   text: L.tr("Some codec libraries come from openSUSE, others from Packman. That breaks video playback. All of them are switched to Packman."),
                   button: L.tr("Switch to Packman") },
        nvidia: { icon: "nvidia", title: L.tr("NVIDIA driver missing for this kernel"),
                  text: L.tr("The NVIDIA kernel module is not built for the running kernel, so the desktop runs without the NVIDIA driver. It is installed again; restart afterwards."),
                  button: L.tr("Reinstall") },
        units: { icon: "dialog-error", title: L.tr("Services that failed to start"),
                 text: L.tr("These background services stopped with an error. They are restarted. If one keeps failing, create a bug report below."),
                 button: L.tr("Restart") },
        space: { icon: "drive-harddisk", title: L.tr("Little free disk space"),
                 text: L.tr("Updates can fail when the disk is full. Old snapshots, the package cache and unused Flatpak runtimes are removed."),
                 button: L.tr("Free space") },
        flathub: { icon: "flatpak-discover", title: L.tr("Flathub is missing"),
                   text: L.tr("Discover cannot show Flatpak apps without Flathub. It is added again."),
                   button: L.tr("Add Flathub") },
        error: { icon: "dialog-error", title: L.tr("The check itself failed"),
                 text: L.tr("Please create a bug report below."), button: "" }
    })

    function doFix(f) {
        if (f.id === "units") {
            // user units are restarted without a password (backend.fix)
            page.app.lastRun = null
            backend.fix(f.fix)
        } else {
            page.app.runAction(f.fix, [])
        }
    }

    Component.onCompleted: if (!backend.checked) backend.checkSystem()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeader { text: L.tr("Check") }

        SettingCard {
            iconName: backend.checking ? "view-refresh"
                      : !backend.checked ? "system-search"
                      : backend.findings.length === 0 ? "checkmark" : "dialog-warning"
            title: backend.checking ? L.tr("Checking the system …")
                   : !backend.checked ? L.tr("System check")
                   : backend.findings.length === 0 ? L.tr("No known problems found")
                   : L.tr("Problems found: %1").replace("%1", backend.findings.length)
            subtitle: L.tr("Looks for common problems: package database, repositories, missing dependencies, codec mix, NVIDIA module, failed services, disk space and Flathub.")
            QQC2.BusyIndicator {
                visible: backend.checking
                running: visible
            }
            QQC2.Button {
                enabled: !backend.checking && !backend.busy
                text: L.tr("Check again")
                icon.name: "view-refresh"
                onClicked: backend.checkSystem()
            }
        }

        Repeater {
            model: backend.findings
            delegate: SettingCard {
                required property var modelData
                readonly property var t: page.texts[modelData.id] || page.texts.error
                iconName: t.icon
                title: t.title
                subtitle: t.text
                status: modelData.items.join(", ")
                statusType: 2
                QQC2.Button {
                    visible: t.button !== "" && (modelData.fix !== "" || modelData.userOnly)
                    enabled: !backend.busy
                    text: t.button
                    icon.name: "tools-wizard"
                    onClicked: page.doFix(modelData)
                }
                QQC2.Button {
                    visible: modelData.id === "deps" && page.st.hasMyrlyn === true
                    text: "Myrlyn"
                    onClicked: backend.launch("myrlyn")
                }
            }
        }

        SectionHeader { text: L.tr("Tools") }

        SettingCard {
            iconName: "view-refresh"
            title: L.tr("Refresh repositories")
            subtitle: L.tr("Reloads the package lists. Helps when Discover or an installation reports outdated or broken repository data.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Refresh")
                onClicked: page.app.runAction("repo-refresh", [])
            }
        }
        SettingCard {
            iconName: "edit-clear-all"
            title: L.tr("Clean package cache")
            subtitle: L.tr("Deletes downloaded package files and cached repository data to free disk space.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Clean")
                onClicked: page.app.runAction("cache-clean", [])
            }
        }
        SettingCard {
            iconName: "flatpak-discover"
            title: L.tr("Flatpak cleanup")
            subtitle: L.tr("Removes runtimes no app needs anymore, or repairs a broken Flatpak installation.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Remove unused")
                onClicked: page.app.runAction("flatpak-unused", [])
            }
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Repair")
                onClicked: page.app.runAction("flatpak-repair", [])
            }
        }
        SettingCard {
            iconName: "package-reinstall"
            fallbackIcon: "package-x-generic"
            title: L.tr("Rebuild package database")
            subtitle: L.tr("Helps when installing or updating stops with an \"rpmdb\" error.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Rebuild")
                onClicked: page.app.runAction("repair-rpmdb", [])
            }
        }
        SettingCard {
            iconName: "system-reboot"
            title: L.tr("Rebuild boot files")
            subtitle: L.tr("Creates the initramfs of every kernel and the boot menu again. Helps when the system hangs at startup or a driver is missing after a kernel update.")
            QQC2.Button {
                enabled: !backend.busy
                text: L.tr("Rebuild")
                onClicked: page.app.confirm(
                    L.tr("Rebuild boot files?"),
                    L.tr("This takes a minute or two. Restart the computer afterwards."),
                    L.tr("Rebuild"),
                    () => page.app.runAction("repair-boot", []))
            }
        }
        SettingCard {
            iconName: "document-revert"
            title: L.tr("Go back to an earlier state")
            subtitle: L.tr("If nothing here helps: restart, choose \"Start bootloader from a read-only snapshot\" in the boot menu and pick the state before the problem. NazoOS Update then offers to make that state permanent.")
            QQC2.Button {
                visible: page.st.hasBtrfsAssistant === true
                text: "Btrfs Assistant"
                onClicked: backend.launch("btrfs-assistant")
            }
        }

        SectionHeader { text: L.tr("Get help") }

        SettingCard {
            iconName: "tools-report-bug"
            title: L.tr("Bug report")
            subtitle: L.tr("Saves system information, errors since startup, repositories and recent updates to a text file in your home folder. Look through it before you share it: it contains device names and your user name.")
            QQC2.Button {
                text: L.tr("Create report")
                icon.name: "document-save"
                onClicked: {
                    const path = backend.saveReport()
                    if (path !== "")
                        page.app.showPassiveNotification(
                            L.tr("Saved: %1").replace("%1", path), "long",
                            L.tr("Show"),
                            () => page.app.openUrl("file://" + path.substring(0, path.lastIndexOf("/"))))
                }
            }
            QQC2.Button {
                text: L.tr("Report on GitHub")
                icon.name: "internet-services"
                onClicked: page.app.openUrl(page.app.repoUrl + "/issues/new")
            }
        }
    }
}
