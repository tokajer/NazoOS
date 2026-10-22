# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Performance: sched_ext scheduler, kernel options, USB polling rate."""

import re
from pathlib import Path

from nazoos_common import helper, proc
from nazoos_common.grub import cmdline_set
from nazoos_common.helper import set_var, write_atomic

from .. import catalog, probes
from ..pollrate import (INTERVALS, MAXLEN, PARAM, SYSFS, format_overrides,
                        from_cmdline)
from .base import ZYPPER_IN, Fail, arg, say

SCX_DEFAULT = Path("/etc/default/scx")


def scx_enable(args):
    sched = arg(args, 0, catalog.SCX_SCHEDULERS)
    if not proc.rpm_installed("scx"):
        helper.run(ZYPPER_IN + ["scx"])
    if not Path("/usr/bin", sched).exists():
        raise Fail("{scheduler} is not part of the installed scx package",
                   scheduler=sched)
    text = SCX_DEFAULT.read_text() if SCX_DEFAULT.exists() else ""
    write_atomic(SCX_DEFAULT, set_var(text, "SCX_SCHEDULER", sched))
    say(f"{SCX_DEFAULT}: SCX_SCHEDULER={sched}")
    helper.run(["systemctl", "enable", "scx.service"])
    helper.run(["systemctl", "restart", "scx.service"])


def scx_disable(_args):
    helper.run(["systemctl", "disable", "--now", "scx.service"])


def kparam(args):
    item = catalog.by_id(catalog.KERNEL_PARAMS, arg(args, 0))
    if item is None:
        raise Fail("unknown kernel option")
    enable = arg(args, 1, ("on", "off")) == "on"
    cmdline_set(item["param"].split("=")[0],
                item["param"] if enable else None)
    say("The change takes effect after a restart.")


def pollrate(args):
    """USB polling rate of one device (kernel-nazoos patch 0022)."""
    sysfs = Path(SYSFS)
    if not sysfs.exists():
        raise Fail("needs the NazoOS kernel")
    vidpid = arg(args, 0)
    if not re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{4}", vidpid):
        raise Fail("invalid device id")
    ms = int(arg(args, 1, [str(i) for i in INTERVALS]))
    connected = vidpid in {d["id"] for d in probes.usb_input_devices()}
    value = ""

    def change(options):
        nonlocal value
        overrides = from_cmdline(options)
        if ms == 0:
            overrides.pop(vidpid, None)
        elif vidpid in overrides or connected:
            overrides[vidpid] = ms
        else:
            raise Fail("this device is not connected")
        value = format_overrides(overrides)
        if len(value) > MAXLEN:
            raise Fail("too many devices with their own polling rate; reset "
                       "one of them to the device default first")
        return f"{PARAM}={value}" if value else None

    cmdline_set(PARAM, change)
    # Now as well, not only after a restart: usbcore reads the list when a
    # device is plugged in. An empty write would not reach the kernel
    sysfs.write_text(value or "\n")
    say("Unplug the device and plug it in again to use the new rate.")
