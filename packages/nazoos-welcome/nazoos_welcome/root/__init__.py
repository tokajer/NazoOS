# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-welcome, run by helper/nazoos-welcome-helper.

Only fixed actions with ids from catalog.py are accepted. Package names,
paths and commands never come from the caller.
"""

from . import (apps, drivers, drives, kernel_switch, maintenance,
               mok_queue, repair_fixes, session, tuning)

ACTIONS = {
    "codecs-install": drivers.codecs_install,
    "nvidia-install": drivers.nvidia_install,
    "rocm-install": drivers.rocm_install,
    "rocm-remove": drivers.rocm_remove,
    "deck-install": drivers.deck_install,
    "session-boot-mode": session.session_boot_mode,
    "scx-enable": tuning.scx_enable,
    "scx-disable": tuning.scx_disable,
    "kparam": tuning.kparam,
    "pollrate": tuning.pollrate,
    "kernel-install": kernel_switch.kernel_install,
    "kernel-only": kernel_switch.kernel_only,
    "kernel-restore": kernel_switch.kernel_restore,
    "kernel-remove": kernel_switch.kernel_remove,
    "mok-import": mok_queue.mok_import,
    "app-install": apps.app_install,
    "app-remove": apps.app_remove,
    "service": maintenance.service,
    "system-update": maintenance.system_update,
    "repo-refresh": maintenance.repo_refresh,
    "cache-clean": maintenance.cache_clean,
    "flatpak-unused": maintenance.flatpak_unused,
    "flatpak-repair": maintenance.flatpak_repair,
    "snapshot": maintenance.snapshot,
    "channel": maintenance.channel,
    "repair-repos": repair_fixes.repair_repos,
    "repair-rpmdb": repair_fixes.repair_rpmdb,
    "repair-key": repair_fixes.repair_key,
    "repair-deps": repair_fixes.repair_deps,
    "repair-packman": repair_fixes.repair_packman,
    "repair-nvidia": repair_fixes.repair_nvidia,
    "repair-units": repair_fixes.repair_units,
    "repair-space": repair_fixes.repair_space,
    "repair-flathub": repair_fixes.repair_flathub,
    "repair-boot": repair_fixes.repair_boot,
    "automount-add": drives.automount_add,
    "automount-remove": drives.automount_remove,
}
