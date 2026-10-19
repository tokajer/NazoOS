# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Performance: sched_ext scheduler, kernel options, USB polling rate."""

import re
from pathlib import Path

from .. import catalog
from .base import (ZYPPER_IN, Fail, arg, cmdline, cmdline_set,
                   rpm_installed, run, say)

SCX_DEFAULT = Path("/etc/default/scx")
USB_DEVICES = Path("/sys/bus/usb/devices")


def scx_enable(args):
    sched = arg(args, 0, catalog.SCX_SCHEDULERS)
    if not rpm_installed("scx"):
        run(ZYPPER_IN + ["scx"])
    if not Path("/usr/bin", sched).exists():
        raise Fail("{scheduler} is not part of the installed scx package",
                   scheduler=sched)
    lines = SCX_DEFAULT.read_text().splitlines() if SCX_DEFAULT.exists() \
        else []
    out, done = [], False
    for line in lines:
        if re.match(r"\s*SCX_SCHEDULER\s*=", line):
            if not done:
                out.append(f"SCX_SCHEDULER={sched}")
                done = True
        else:
            out.append(line)
    if not done:
        out.append(f"SCX_SCHEDULER={sched}")
    SCX_DEFAULT.write_text("\n".join(out) + "\n")
    say(f"{SCX_DEFAULT}: SCX_SCHEDULER={sched}")
    run(["systemctl", "enable", "scx.service"])
    run(["systemctl", "restart", "scx.service"])


def scx_disable(_args):
    run(["systemctl", "disable", "--now", "scx.service"])


def kparam(args):
    item = catalog.by_id(catalog.KERNEL_PARAMS, arg(args, 0))
    if item is None:
        raise Fail("unknown kernel option")
    enable = arg(args, 1, ("on", "off")) == "on"
    cmdline_set(item["param"].split("=")[0],
                item["param"] if enable else None)
    say("The change takes effect after a restart.")


def usb_ids():
    """VID:PID of all connected USB devices."""
    ids = set()
    for dev in USB_DEVICES.glob("*"):
        try:
            ids.add((dev / "idVendor").read_text().strip() + ":"
                    + (dev / "idProduct").read_text().strip())
        except OSError:
            pass
    return ids


def pollrate(args):
    """USB polling rate of one device (kernel-nazoos patch 0022)."""
    sysfs = Path(catalog.POLLRATE_SYSFS)
    if not sysfs.exists():
        raise Fail("needs the NazoOS kernel")
    vidpid = arg(args, 0)
    if not re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{4}", vidpid):
        raise Fail("invalid device id")
    ms = int(arg(args, 1, [str(i) for i in catalog.POLLRATE_INTERVALS]))
    overrides = {}
    for opt in cmdline()[2]:
        if opt.startswith(catalog.POLLRATE_PARAM + "="):
            overrides = catalog.pollrate_parse(opt.split("=", 1)[1])
    if ms == 0:
        overrides.pop(vidpid, None)
    elif vidpid in usb_ids() or vidpid in overrides:
        overrides[vidpid] = ms
    else:
        raise Fail("this device is not connected")
    value = catalog.pollrate_format(overrides)
    if len(value) > catalog.POLLRATE_MAXLEN:
        raise Fail("too many devices with their own polling rate; reset one "
                   "of them to the device default first")
    cmdline_set(catalog.POLLRATE_PARAM,
                f"{catalog.POLLRATE_PARAM}={value}" if value else None)
    # Now as well, not only after a restart: usbcore reads the list when a
    # device is plugged in. An empty write would not reach the kernel
    sysfs.write_text(value or "\n")
    say("Unplug the device and plug it in again to use the new rate.")
