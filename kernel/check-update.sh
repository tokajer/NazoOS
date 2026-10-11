#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Is there a new kernel for kernel-nazoos? Compares SUSE's kernel-source
# branch stable (= Kernel:stable) with the package in OBS. Reads two files
# from GitHub, no clone. Needs curl and a logged-in osc.
#
# Output (key=value, for humans and for $GITHUB_OUTPUT):
#   series=7.2     Linux series on kernel-source stable
#   pinned=7.2     KERNEL_SERIES in make-obs-package.sh (patches.list)
#   upstream=7.2.10  newest stable release on kernel-source stable
#   obs=7.2.9      version of kernel-nazoos in OBS
set -euo pipefail

PROJECT=home:Tokajer:nazoos:kernel
RAW=https://raw.githubusercontent.com/SUSE/kernel-source/stable

here=$(cd "$(dirname "$0")" && pwd)

series=$(curl -fsSL "$RAW/rpm/config.sh" | sed -nE 's/^SRCVERSION=([0-9.]+)$/\1/p')
# Stable releases are patches.kernel.org/<version>-NNN-*.patch in
# series.conf; the newest one is the version (like compute-PATCHVERSION.sh).
# None yet (fresh series): the version is the series itself
upstream=$(curl -fsSL "$RAW/series.conf" |
  sed -nE 's#^\s*patches\.kernel\.org/([0-9]+\.[0-9]+\.[0-9]+)-.*#\1#p' |
  sort -uV | tail -1)
pinned=$(sed -nE 's/^KERNEL_SERIES=([0-9.]+).*/\1/p' "$here/make-obs-package.sh")
obs=$(osc cat "$PROJECT" kernel-source kernel-nazoos.spec |
  sed -nE 's/^%define patchversion ([0-9.]+)$/\1/p')

[ -n "$series" ] && [ -n "$pinned" ] && [ -n "$obs" ] ||
  { echo "error: could not read a version (series=$series pinned=$pinned obs=$obs)" >&2; exit 1; }

echo "series=$series"
echo "pinned=$pinned"
echo "upstream=${upstream:-$series}"
echo "obs=$obs"
