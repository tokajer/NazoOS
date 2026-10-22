# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The root helpers and the probes stay free of Qt."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CODE = """
import nazoos_welcome.root, nazoos_update.root, nazoos_welcome.probes
import nazoos_welcome.repair_checks, nazoos_welcome.user_actions
import nazoos_welcome.report
import nazoos_common.launcher, nazoos_common.shellconf
import nazoos_common.kmp_sync, nazoos_welcome.hw, nazoos_welcome.system
import nazoos_common.files, nazoos_welcome.query
import sys
assert not any(m.startswith("PySide6") for m in sys.modules)
"""


def test_root_and_probe_code_does_not_import_qt():
    # A subprocess: the pytest process has PySide6 loaded by test_qt
    path = os.pathsep.join(
        str(ROOT / "packages" / p)
        for p in ("nazoos-common", "nazoos-welcome", "nazoos-update"))
    r = subprocess.run([sys.executable, "-c", CODE], capture_output=True,
                       text=True, env=dict(os.environ, PYTHONPATH=path))
    assert r.returncode == 0, r.stderr
