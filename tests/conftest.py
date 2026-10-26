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


# zypper's refresh output for a repo with an untrusted key (real, shortened)
KEY_OUTPUT = """\
Retrieving repository 'keytest' metadata [..
Looking for gpg keys in repository Some Name (beta).
  gpgkey=https://download.opensuse.org/repositories/games:/tools/openSUSE_Tumbleweed/repodata/repomd.xml.key
..

New repository or package signing key received:

  Repository:       Some Name (beta)
  Key Fingerprint:  4AFF 5EF3 C350 A53A 05D6 BA0D 1E8E DBE8 58DD EB32
  Key Name:         games:tools OBS Project <games:tools@build.opensuse.org>
  Key Algorithm:    DSA 1024
  Rpm Name:         gpg-pubkey-58ddeb32-68091727

    Note: Signing data enables ...
  Repository:       Not This One
Do you want to reject the key, trust temporarily, or trust always? [r/t/a/?] (r): r
error]
Repository 'keytest' is invalid.
History:
 - Signature verification failed for repomd.xml
Could not refresh the repositories because of errors.
"""
KEY_FPR = "4AFF5EF3C350A53A05D6BA0D1E8EDBE858DDEB32"
KEY_URL = ("https://download.opensuse.org/repositories/games:/tools/"
           "openSUSE_Tumbleweed/repodata/repomd.xml.key")
