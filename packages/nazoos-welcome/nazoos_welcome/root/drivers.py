# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drivers, codecs and handheld support."""

import json

from nazoos_common import helper, kernel, proc
from nazoos_common.files import write_atomic
from nazoos_common.helper import Fail, arg, say
from nazoos_common.zypper import ZYPPER

from .. import system
from .base import repo_in_use
from .packman import packman_switch


def _packman_installed():
    return "packman" in helper.output(
        ["rpm", "-qa", "--qf", "%{VENDOR}\n"]).lower()


def codecs_install(_args):
    with repo_in_use(
            "/packman/", system.PACKMAN_ALIAS,
            ["--refresh", "--priority", system.PACKMAN_PRIORITY,
             "--name", "Packman", system.packman_url()],
            _packman_installed, system.PACKMAN_KEY) as alias:
        packman_switch(alias)
        helper.install(["--from", alias] + system.PACKMAN_CODECS)
    helper.install(system.OSS_CODECS)


def nvidia_install(args):
    variant = arg(args, 0, system.NVIDIA_DRIVERS)
    drivers = system.NVIDIA_DRIVERS[variant]["packages"]
    if variant == "legacy" and proc.rpm_installed(kernel.KERNEL_PACKAGE):
        raise Fail("the driver for older NVIDIA cards only exists for the "
                   "openSUSE kernel; remove the NazoOS kernel on the Kernel "
                   "page first")
    with repo_in_use(
            "://download.nvidia.com/", system.NVIDIA_REPO_ALIAS,
            ["--refresh", "--name", "NVIDIA", system.NVIDIA_REPO_URL],
            lambda: any(proc.rpm_installed(p) for p in drivers),
            system.NVIDIA_KEY):
        helper.install(drivers)
    say("Restart the computer to load the NVIDIA driver.")


def _policies(text):
    """The policies object of a Firefox policies.json text; a missing,
    empty or broken file counts as no policies."""
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict) or not isinstance(data.get("policies"), dict):
        data = {"policies": {}}
    return data


def vaapi_policies(text):
    """policies.json text with our Firefox preferences added; everything
    else in the file stays."""
    data = _policies(text)
    prefs = data["policies"].setdefault("Preferences", {})
    if not isinstance(prefs, dict):
        prefs = data["policies"]["Preferences"] = {}
    for key, value in system.NVIDIA_VAAPI_PREFS.items():
        prefs[key] = {"Value": value, "Status": "default"}
    return json.dumps(data, indent=2) + "\n"


def vaapi_policies_without(text):
    """policies.json text without our preferences, or None when nothing
    else is left in the file."""
    data = _policies(text)
    prefs = data["policies"].get("Preferences")
    if isinstance(prefs, dict):
        for key in system.NVIDIA_VAAPI_PREFS:
            prefs.pop(key, None)
        if not prefs:
            del data["policies"]["Preferences"]
    if not data["policies"] and len(data) == 1:
        return None
    return json.dumps(data, indent=2) + "\n"


def _read(path):
    return path.read_text() if path.exists() else ""


def chromium_vaapi_write():
    """Our patched .desktop copies for every installed Chromium browser;
    a file there that we did not write stays untouched."""
    for _source, target, text in system.chromium_entries():
        if target.exists() and not system.desktop_is_ours(target):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(target, text)


def chromium_vaapi_remove():
    for names in system.CHROMIUM_BROWSERS.values():
        for name in names:
            target = system.LOCAL_APPS / name
            if system.desktop_is_ours(target):
                target.unlink()


def nvidia_vaapi_enable(_args):
    if not any(proc.rpm_installed(d["video"])
               for d in system.NVIDIA_DRIVERS.values()):
        raise Fail("install the NVIDIA driver first")
    helper.install([system.NVIDIA_VAAPI_PACKAGE])
    system.NVIDIA_VAAPI_ENV.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(system.NVIDIA_VAAPI_ENV, system.NVIDIA_VAAPI_ENV_TEXT)
    system.FIREFOX_POLICIES.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(system.FIREFOX_POLICIES,
                 vaapi_policies(_read(system.FIREFOX_POLICIES)))
    chromium_vaapi_write()
    say("Log out and in again, then restart the browser.")


def nvidia_vaapi_disable(_args):
    system.NVIDIA_VAAPI_ENV.unlink(missing_ok=True)
    chromium_vaapi_remove()
    if system.FIREFOX_POLICIES.exists():
        rest = vaapi_policies_without(_read(system.FIREFOX_POLICIES))
        if rest is None:
            system.FIREFOX_POLICIES.unlink()
        else:
            write_atomic(system.FIREFOX_POLICIES, rest)
    if proc.rpm_installed(system.NVIDIA_VAAPI_PACKAGE):
        helper.run(ZYPPER + ["remove", "--clean-deps",
                             system.NVIDIA_VAAPI_PACKAGE])
    say("Log out and in again, then restart the browser.")


def rocm_install(_args):
    helper.install(system.ROCM_PACKAGES)
    say("Restart programs like Blender so they find the GPU.")


def rocm_remove(_args):
    pkgs = [p for p in system.ROCM_PACKAGES if proc.rpm_installed(p)]
    if pkgs:
        helper.run(ZYPPER + ["remove", "--clean-deps"] + pkgs)


def deck_install(_args):
    helper.run(ZYPPER + ["refresh"])
    helper.install(["--type", "pattern", system.DECK_PATTERN])

