# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared fixtures."""

import subprocess

import pytest

from nazoos_common import grub, helper, proc


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
    # The root modules call helper.run / helper.output / proc.rpm_installed
    # through their modules
    monkeypatch.setattr(helper, "run", fake.run)
    monkeypatch.setattr(helper, "output", fake.output)
    monkeypatch.setattr(proc, "rpm_installed", fake.rpm_installed)

    def real_command(cmd, *_args, **_kw):
        pytest.fail(f"real command in a root test: {cmd}")

    # A probe the test forgot to patch must not reach the machine
    monkeypatch.setattr(subprocess, "run", real_command)
    monkeypatch.setattr(subprocess, "Popen", real_command)
    monkeypatch.setattr(grub, "GRUB_DEFAULT_FILE", tmp_path / "grub-default")
    monkeypatch.setattr(grub, "GRUB_LOCK", tmp_path / "grub.lock")
    monkeypatch.setattr(grub, "GRUB_CFG", tmp_path / "grub.cfg")
    return fake
