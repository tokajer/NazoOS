# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Root actions of nazoos-welcome, run by helper/nazoos-welcome-helper.

Only fixed actions with ids from catalog.py are accepted. Package names,
paths and commands never come from the caller.
"""

from . import (apps, drivers, drives, kernel_switch, maintenance,
               mok_queue, repairs, tuning)

ACTIONS = {
    "codecs-install": drivers.codecs_install,
    "nvidia-install": drivers.nvidia_install,
    "rocm-install": drivers.rocm_install,
    "rocm-remove": drivers.rocm_remove,
    "deck-install": drivers.deck_install,
    "session-boot-mode": drivers.session_boot_mode,
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
    "repair-repos": repairs.repair_repos,
    "repair-rpmdb": repairs.repair_rpmdb,
    "repair-deps": repairs.repair_deps,
    "repair-packman": repairs.repair_packman,
    "repair-nvidia": repairs.repair_nvidia,
    "repair-units": repairs.repair_units,
    "repair-space": repairs.repair_space,
    "repair-flathub": repairs.repair_flathub,
    "repair-boot": repairs.repair_boot,
    "automount-add": drives.automount_add,
    "automount-remove": drives.automount_remove,
}
