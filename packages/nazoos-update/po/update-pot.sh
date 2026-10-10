#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Regenerates po/nazoos-update.pot from the sources and merges it into
# every po/*.po. Run from the package directory after changing UI texts.
set -euo pipefail
cd "$(dirname "$0")/.."

pot=po/nazoos-update.pot
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# QML: L.tr("...") and L.trn("singular", "plural", n)
xgettext --from-code=UTF-8 --language=JavaScript --keyword=tr \
  --keyword=trn:1,2 --package-name=nazoos-update \
  --output="$tmp/qml.pot" qml/*.qml
# Python: _("...") and ngettext("...", "...", n); ACTION_LABELS via a list
xgettext --from-code=UTF-8 --language=Python --keyword=_ \
  --keyword=ngettext:1,2 --output="$tmp/py.pot" nazoos_update/*.py
python3 - "$tmp/labels.pot" <<'PY'
import re, sys
src = open("nazoos_update/backend.py").read()
block = src.split("ACTION_LABELS = {", 1)[1].split("}", 1)[0]
out = ['msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n']
for t in re.findall(r':\s*"([^"]+)"', block):
    out.append(f'#: nazoos_update/backend.py\nmsgid "{t}"\nmsgstr ""\n')
open(sys.argv[1], "w").write("\n".join(out))
PY
msgcat --use-first --sort-by-file "$tmp/qml.pot" "$tmp/py.pot" \
  "$tmp/labels.pot" -o "$pot"

shopt -s nullglob
for po in po/*.po; do
  msgmerge --quiet --update --backup=none --no-fuzzy-matching "$po" "$pot"
done
