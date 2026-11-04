#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Is there a new kernel for kernel-nazoos? Compares the kernel-source of
# openSUSE:Slowroll (kernel-nazoos is built from exactly that commit, see
# make-obs-package.sh) with the package in OBS. Reads one spec from the
# anonymous OBS API, no clone. Needs curl and a logged-in osc.
#
# Output (key=value, for humans and for $GITHUB_OUTPUT):
#   series=7.3     Linux series of Slowroll's kernel-source
#   pinned=7.3     KERNEL_SERIES in make-obs-package.sh (patches.list)
#   upstream=7.3.1 kernel version of Slowroll's kernel-source
#   commit=8815…   SUSE/kernel-source commit it was made from
#   obs=7.3.1      version of kernel-nazoos in OBS
set -euo pipefail

PROJECT=home:Tokajer:nazoos:kernel
SLOWROLL_SPEC='https://api.opensuse.org/public/source/openSUSE:Slowroll/kernel-source/kernel-default.spec?expand=1'

here=$(cd "$(dirname "$0")" && pwd)

spec=$(curl -fsSL --retry 3 "$SLOWROLL_SPEC")
series=$(sed -nE 's/^%define srcversion ([0-9.]+)$/\1/p' <<<"$spec")
upstream=$(sed -nE 's/^%define patchversion ([0-9.]+)$/\1/p' <<<"$spec")
commit=$(sed -nE 's/^%define git_commit ([0-9a-f]{40})$/\1/p' <<<"$spec")
pinned=$(sed -nE 's/^KERNEL_SERIES=([0-9.]+).*/\1/p' "$here/make-obs-package.sh")
obs=$(osc cat "$PROJECT" kernel-source kernel-nazoos.spec |
  sed -nE 's/^%define patchversion ([0-9.]+)$/\1/p')

[ -n "$series" ] && [ -n "$upstream" ] && [ -n "$commit" ] && [ -n "$pinned" ] && [ -n "$obs" ] ||
  { echo "error: could not read a version (series=$series upstream=$upstream commit=$commit pinned=$pinned obs=$obs)" >&2; exit 1; }

echo "series=$series"
echo "pinned=$pinned"
echo "upstream=$upstream"
echo "commit=$commit"
echo "obs=$obs"
