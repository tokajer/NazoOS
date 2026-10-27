#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packages of a project that .obs/workflows.yml rebuilds on a push.

Usage: release-packages.py PROJECT
Prints the package of every trigger_services step whose project is PROJECT,
one per line, without nazoos-image (the release ISO has its own package in
:release, see release.yml). Matches the text instead of parsing it with
PyYAML (not on the runner); the order of "project:" and "package:" inside a
step does not matter. Exits 1 when there is no package.
"""

import re
import sys
from pathlib import Path

EXCLUDED = {"nazoos-image"}
WORKFLOWS = Path(__file__).resolve().parents[2] / ".obs/workflows.yml"
# A step is the indented key lines after "- trigger_services:" (comments
# allowed); the next "- " item or the dedented "filters:" ends it
STEP = re.compile(
    r"^\s*-\s+trigger_services:[ ]*\n((?:[ ]{6,}\w+:.*\n|[ ]*#.*\n)+)", re.M)
FIELD = re.compile(r"^\s+(project|package):\s*(\S+)", re.M)


def packages(text, project):
    found = []
    for block in STEP.findall(text):
        step = {k: v.strip("'\"") for k, v in FIELD.findall(block)}
        if (step.get("project") == project and step.get("package")
                and step["package"] not in EXCLUDED):
            found.append(step["package"])
    return found


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    found = packages(WORKFLOWS.read_text(), argv[1])
    if not found:
        sys.exit(f"no package found for {argv[1]} in {WORKFLOWS}")
    print("\n".join(found))


if __name__ == "__main__":
    main(sys.argv)
