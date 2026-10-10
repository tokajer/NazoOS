#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Regenerates po/nazoos-welcome.pot from the sources and merges it into
# every po/*.po. Run from the package directory after changing UI texts.
set -euo pipefail
cd "$(dirname "$0")/.."

pot=po/nazoos-welcome.pot
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# QML: L.tr("...")
xgettext --from-code=UTF-8 --language=JavaScript --keyword=tr \
  --package-name=nazoos-welcome --output="$tmp/qml.pot" qml/*.qml qml/*/*.qml
# Python: gettext("...") in the backend
xgettext --from-code=UTF-8 --language=Python --keyword=gettext \
  --output="$tmp/py.pot" nazoos_welcome/*.py
# Catalog: app, service and option names/summaries, ACTION_LABELS
python3 - "$tmp/catalog.pot" <<'PY'
import sys
sys.path.insert(0, ".")
from nazoos_welcome import catalog, backend
texts = []
for a in catalog.APPS:
    texts.append(a["summary"])
for s in catalog.SERVICES + catalog.KERNEL_PARAMS:
    texts += [s["name"], s["summary"]]
texts += list(backend.ACTION_LABELS.values())
seen, out = set(), []
for t in texts:
    if t not in seen:
        seen.add(t)
        esc = t.replace("\\", "\\\\").replace('"', '\\"')
        out.append(f'#: nazoos_welcome/catalog.py\nmsgid "{esc}"\nmsgstr ""\n')
open(sys.argv[1], "w").write(
    'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
    + "\n".join(out))
PY
msgcat --use-first --sort-by-file "$tmp/qml.pot" "$tmp/py.pot" \
  "$tmp/catalog.pot" -o "$pot"

shopt -s nullglob
for po in po/*.po; do
  msgmerge --quiet --update --backup=none --no-fuzzy-matching "$po" "$pot"
done
