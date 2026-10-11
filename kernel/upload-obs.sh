#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Commits the package made by make-obs-package.sh to OBS
# (home:Tokajer:nazoos:kernel/kernel-source). OBS then builds the kernel
# and, after it, the KMPs. Used by hand and by the GitHub workflow
# kernel-update.yml.
#
# Usage: ./upload-obs.sh [WORKDIR]   (same WORKDIR as make-obs-package.sh)
# Needs: osc (logged in), rsync
set -euo pipefail

PROJECT=home:Tokajer:nazoos:kernel
PACKAGE=kernel-source

WORK=$(realpath -m "${1:-$HOME/nazoos-kernel}")
out=$WORK/kernel-source-nazoos
co=$WORK/obs/$PROJECT/$PACKAGE

[ -f "$out/kernel-nazoos.spec" ] ||
  { echo "missing $out/kernel-nazoos.spec: run make-obs-package.sh first" >&2; exit 1; }

# osc checkout: reuse it, else create it (first run, CI)
if [ -d "$co/.osc" ]; then
  (cd "$co" && osc up)
else
  mkdir -p "$WORK/obs"
  (cd "$WORK/obs" && osc co "$PROJECT" "$PACKAGE")
fi

rsync -a --delete --exclude .osc "$out/" "$co/"
cd "$co"
osc addremove
if [ -z "$(osc status)" ]; then
  echo "OBS already has this package, nothing to commit"
  exit 0
fi
osc status
version=$(sed -n 's/^%define patchversion //p' kernel-nazoos.spec)
osc ci -m "Update to Linux $version"
echo "Committed: OBS builds kernel-nazoos $version, then the KMPs"
