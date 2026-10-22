# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared fixtures."""

import importlib
import pkgutil

import pytest

import nazoos_welcome.root
from nazoos_common import grub, helper

# Every root module, so a new one cannot run real commands in tests
ROOT_MODULES = [m.name for m in pkgutil.iter_modules(nazoos_welcome.root.__path__)]


class FakeRoot:
    """Records the commands of the root actions instead of running them.

    rc: {command word: exit code} or a function cmd -> exit code (default
    0). out: function cmd -> stdout (default ""). installed: package
    names rpm_installed() answers True for."""

    def __init__(self):
        self.calls = []
        self.rc = {}
        self.out = lambda cmd: ""
        self.installed = set()

    def code(self, cmd):
        if callable(self.rc):
            return self.rc(cmd)
        return next((v for k, v in self.rc.items() if k in cmd), 0)

    def run(self, cmd, check=True, on_line=None):
        self.calls.append(list(cmd))
        rc = self.code(cmd)
        if check and rc != 0:
            raise helper.Fail("'{cmd}' failed (exit code {rc})",
                              cmd=cmd[0], rc=rc)
        return rc

    def output(self, cmd):
        return self.out(cmd)

    def rpm_installed(self, name):
        return name in self.installed


@pytest.fixture
def fake_root(monkeypatch, tmp_path):
    fake = FakeRoot()
    # grub.* and kernel.* run helper.run / helper.output
    monkeypatch.setattr(helper, "run", fake.run)
    monkeypatch.setattr(helper, "output", fake.output)
    monkeypatch.setattr(grub, "GRUB_DEFAULT_FILE", tmp_path / "grub-default")
    monkeypatch.setattr(grub, "GRUB_LOCK", tmp_path / "grub.lock")
    monkeypatch.setattr(grub, "GRUB_CFG", tmp_path / "grub.cfg")
    for name in ROOT_MODULES:
        module = importlib.import_module(f"nazoos_welcome.root.{name}")
        for attr in ("run", "output", "rpm_installed"):
            if hasattr(module, attr):
                monkeypatch.setattr(module, attr, getattr(fake, attr))
    return fake
