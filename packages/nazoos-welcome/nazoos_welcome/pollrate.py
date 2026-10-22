# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""USB polling rate overrides on the kernel command line (no Qt here)."""

# USB polling rate per device (kernel-nazoos patch 0022, like Nobara's
# custom-device-pollrates). Kernel option VID:PID:ms[,VID:PID:ms...];
# usbcore loads from the initrd, so only the command line keeps it over a
# restart.
# The sysfs file exists only in kernel-nazoos and holds at most 127 chars.
PARAM = "usbcore.interrupt_interval_override"
SYSFS = "/sys/module/usbcore/parameters/interrupt_interval_override"
MAXLEN = 127
# Interval in ms: 0 = device default, then 125, 250, 500 and 1000 Hz
INTERVALS = [0, 8, 4, 2, 1]


def parse(value):
    """{"045e:028e": 1, ...} from "045e:028e:1,..." (bad entries dropped)."""
    result = {}
    for entry in value.strip().split(","):
        parts = entry.strip().lower().split(":")
        if (len(parts) == 3 and all(len(p) == 4 for p in parts[:2])
                and all(c in "0123456789abcdef" for c in parts[0] + parts[1])
                and parts[2].isdigit() and int(parts[2]) > 0):
            result[f"{parts[0]}:{parts[1]}"] = int(parts[2])
    return result


def from_cmdline(options):
    """Overrides configured in the kernel options OPTIONS (list), {} if none."""
    overrides = {}
    for opt in options:
        if opt.startswith(PARAM + "="):
            overrides = parse(opt.split("=", 1)[1])
    return overrides


def format_overrides(overrides):
    return ",".join(f"{vp}:{ms}" for vp, ms in sorted(overrides.items()))
