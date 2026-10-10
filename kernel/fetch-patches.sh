#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Downloads the patches listed in patches.list into patches/.
# Run again after changing patches.list (new kernel series).
set -euo pipefail
cd "$(dirname "$0")"

grep -vE '^\s*(#|$)' patches.list | while read -r name url; do
  # Refreshed by us (see the comment in patches.list): nothing to fetch
  if [ "$url" = local ]; then
    [ -f "patches/$name" ] || { echo "error: patches/$name missing" >&2; exit 1; }
    echo "$name  (local)"
    continue
  fi
  echo "$name  <-  $url"
  curl -fsSL --retry 3 -o "patches/$name.tmp" "$url"
  # A commit .patch from GitHub is an mbox: fine for patch -p1 and quilt
  if ! grep -q '^diff --git' "patches/$name.tmp"; then
    echo "error: $url is not a patch" >&2
    rm -f "patches/$name.tmp"
    exit 1
  fi
  mv "patches/$name.tmp" "patches/$name"
done
# Remove patches that are no longer listed
for f in patches/*.patch; do
  [ -e "$f" ] || continue
  grep -qE "^$(basename "$f")\s" patches.list || { echo "removing $f"; rm "$f"; }
done
