# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared fixtures. The import paths come from pyproject.toml."""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_script(path, name):
    """Import a Python script without .py (the root helpers) as a module;
    its main() does not run (__name__ is not "__main__")."""
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def update_helper():
    return load_script(
        ROOT / "packages/nazoos-update/helper/nazoos-update-helper",
        "nazoos_update_helper")
