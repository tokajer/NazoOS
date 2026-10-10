#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Builds the OBS source package of kernel-nazoos (ADR 0007/0008):
#   1. clone SUSE's kernel-source git (branch of Kernel:stable)
#   2. add our patches (patches/) as patches.addon/nazoos-*.patch
#   3. add the flavor x86_64/nazoos: default config + config/nazoos.fragment,
#      new options from the patches via "make olddefconfig"
#   4. scripts/tar-up for x86_64/nazoos only -> $WORK/kernel-source-nazoos
# The result is committed to OBS by hand (see README.md).
#
# Usage: ./make-obs-package.sh [--check] [WORKDIR]
#   --check  only test that all patches apply and the config is complete
# Needs: git, curl, quilt, make, gcc, flex, bison, bc, perl, xz, python3
#   perl-Text-Glob (Tumbleweed: zypper in git curl quilt make gcc flex bison
#   bc perl xz python3 perl-Text-Glob)
set -euo pipefail

BRANCH=stable                 # SUSE/kernel-source branch = Kernel:stable
FLAVOR=nazoos
REPO=https://github.com/SUSE/kernel-source.git

here=$(cd "$(dirname "$0")" && pwd)
check=false
if [ "${1:-}" = --check ]; then check=true; shift; fi
WORK=$(realpath -m "${1:-$HOME/nazoos-kernel}")
src=$WORK/kernel-source
mkdir -p "$WORK"

# --- 1. kernel-source git ---------------------------------------------------
# Partial clone: full history (tar-up writes the .changes from it), file
# contents are fetched on demand
if [ ! -d "$src/.git" ]; then
  git clone --filter=blob:none --branch "$BRANCH" --single-branch "$REPO" "$src"
fi
git -C "$src" fetch origin "$BRANCH"
# Our changes live on a local branch that is rebuilt from scratch every
# time: -f and clean drop what an earlier run left behind
git -C "$src" checkout -q -f -B "$FLAVOR" "origin/$BRANCH"
git -C "$src" clean -q -fd -- patches.addon config
. "$src/rpm/config.sh"        # SRCVERSION, e.g. 7.2
echo "kernel-source $BRANCH: Linux $SRCVERSION"

# --- 2. patches -------------------------------------------------------------
mkdir -p "$src/patches.addon"
{
  echo
  echo "	########################################################"
  echo "	# NazoOS gaming patches (NazoOS/kernel/patches.list)"
  echo "	########################################################"
} >> "$src/series.conf"
grep -vE '^\s*(#|$)' "$here/patches.list" | while read -r name _url; do
  [ -f "$here/patches/$name" ] || { echo "missing patches/$name: run fetch-patches.sh" >&2; exit 1; }
  install -m 644 "$here/patches/$name" "$src/patches.addon/$FLAVOR-$name"
  printf '\tpatches.addon/%s\n' "$FLAVOR-$name" >> "$src/series.conf"
done

# --- 3. flavor --------------------------------------------------------------
cfg=$src/config/x86_64/$FLAVOR
cp "$src/config/x86_64/default" "$cfg"
# Apply the fragment: drop every option it mentions, append its lines
python3 - "$cfg" "$here/config/nazoos.fragment" <<'PY'
import re, sys
cfg, frag = sys.argv[1], sys.argv[2]
opt = re.compile(r"^(?:# )?(CONFIG_[A-Za-z0-9_]+)(?:=| is not set)")
lines = [l.rstrip("\n") for l in open(frag)]
wanted = [l for l in lines if opt.match(l)]
names = {opt.match(l).group(1) for l in wanted}
out = [l for l in open(cfg).read().splitlines()
       if not (opt.match(l) and opt.match(l).group(1) in names)]
open(cfg, "w").write("\n".join(out + wanted) + "\n")
PY
# Register the flavor; "-syms" not set: kernel-syms carries it, KMPs
# (nvidia, xpadneo, xone) are built against it
sed -i "s|^+x86_64\t\tx86_64/default$|&\n+x86_64\t\tx86_64/$FLAVOR|" "$src/config.conf"
grep -q "x86_64/$FLAVOR" "$src/config.conf"
# Summary and description of the kernel-nazoos package (read by mkspec)
cat >> "$src/rpm/package-descriptions" <<'DESC'

=== kernel-nazoos ===
The NazoOS Gaming Kernel

The openSUSE kernel with gaming patches for NazoOS: BORE scheduler,
1000 Hz timer, full preemption, BBRv3, ACS override, v4l2loopback and
handheld drivers (Steam Deck, ROG Ally, MSI Claw, Zotac Zone, Ayaneo,
GPD, OneXPlayer). Installed next to kernel-default.
DESC

# Linux tarball for sequence-patch/tar-up (with signature, they check it)
tar_dir=$WORK/tarballs
mkdir -p "$tar_dir"
major=${SRCVERSION%%.*}
for f in "linux-$SRCVERSION.tar.xz" "linux-$SRCVERSION.tar.sign"; do
  [ -f "$tar_dir/$f" ] || curl -fL --retry 3 -o "$tar_dir/$f" \
    "https://cdn.kernel.org/pub/linux/kernel/v$major.x/$f"
done
export LINUX_TAR_DIR=$tar_dir

# Patch a tree once: shows failing patches, gives us a tree for oldconfig
tree=$WORK/tree
# sequence-patch leaves read-only files and directories behind
[ -d "$tree" ] && chmod -R u+w "$tree"
rm -rf "$tree"
(cd "$src" && scripts/sequence-patch --dir="$tree" --config="x86_64-$FLAVOR")
patched=$(ls -d "$tree"/linux-*-*/ | head -1)
# New options added by the patches: take their defaults, keep the rest.
# Same as SUSE's scripts/run_oldconfig: the dummy tools report a fixed
# "everything supported" toolchain, so the config does not depend on the
# local gcc
chmod 755 "$patched"/scripts/dummy-tools/*
cp "$cfg" "$patched/.config"
make -s -C "$patched" ARCH=x86_64 CROSS_COMPILE=scripts/dummy-tools/ \
  PAHOLE=scripts/dummy-tools/pahole OPENSSL=scripts/dummy-tools/openssl \
  olddefconfig
python3 - "$cfg" "$patched/.config" <<'PY'
import sys
old, new = sys.argv[1], sys.argv[2]
a = set(open(old).read().splitlines())
b = open(new).read().splitlines()
added = [l for l in b if l not in a and l.startswith(("CONFIG_", "# CONFIG_"))]
print("options set by olddefconfig:", *added, sep="\n  ")
PY
cp "$patched/.config" "$cfg"
# The fragment must survive olddefconfig (typo, missing dependency or patch)
while read -r line; do
  case "$line" in
    CONFIG_*) grep -qxF "$line" "$cfg" ;;
    "# CONFIG_"*) sym=${line#\# }; sym=${sym%% *}; ! grep -q "^$sym=" "$cfg" ;;
    *) true ;;
  esac || { echo "error: fragment line lost after olddefconfig: $line" >&2; exit 1; }
done < "$here/config/nazoos.fragment"
echo "patches apply, config x86_64/$FLAVOR complete"
$check && exit 0

# tar-up only takes committed files: commit to the local branch
git -C "$src" add -A config/x86_64/$FLAVOR config.conf series.conf patches.addon \
  rpm/package-descriptions
git -C "$src" -c user.name="NazoOS" -c user.email="nazoos@localhost" \
  commit -q -m "NazoOS: flavor $FLAVOR with gaming patches"

# --- 4. OBS package ---------------------------------------------------------
out=$WORK/kernel-source-$FLAVOR
(cd "$src" && scripts/tar-up --dir="$out" -a x86_64 -f "$FLAVOR")
echo
echo "OBS package files: $out"
echo "Next: copy them into an osc checkout of home:Tokajer:nazoos:devel/kernel-source,"
echo "      osc addremove && osc commit (see NazoOS/kernel/README.md)"
