#!/usr/bin/env bash
# Apply the ChromiumFish fork on top of a vanilla Chromium checkout.
#
# Usage from the root of this repo (where src/ does NOT yet exist):
#
#   1. Follow https://chromium.googlesource.com/chromium/src/+/main/docs/mac_build_instructions.md
#      to get depot_tools and check out Chromium into ./src.
#   2. Sync to the exact commit this fork was authored against:
#         (cd src && git checkout "$(cat ../UPSTREAM_REVISION)")
#         gclient sync --with_branch_heads --reset
#   3. Run this script.
#
# What it does:
#   * Applies patches/chromiumfish.patch (text-only source edits).
#   * Overlays assets/* on top of src/* (icons, fonts, binary asset
#     replacements that don't compress well as patch hunks).
#   * Leaves all other source files untouched.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src"

if [[ ! -d "$SRC" ]]; then
    echo "error: $SRC/ not found. Check out Chromium first (see top of this file)." >&2
    exit 1
fi

UPSTREAM_REV="$(cat "$ROOT/UPSTREAM_REVISION")"
CURRENT_REV="$(cd "$SRC" && git rev-parse HEAD)"
if [[ "$CURRENT_REV" != "$UPSTREAM_REV" ]]; then
    echo "warning: src/ is at $CURRENT_REV but this fork was authored against $UPSTREAM_REV"
    echo "         patches may need manual fixup at hunks that drifted upstream." >&2
fi

echo "=> applying patches/chromiumfish.patch ..."
# git apply --reject returns non-zero on submodule-ref hunks (mode 160000) and a
# handful of other edge cases even when every source-level hunk applied. The real
# signal for failure is the .rej count.
(cd "$SRC" && git apply --reject --whitespace=fix "$ROOT/patches/chromiumfish.patch") || true
REJ_COUNT=$(find "$SRC" -maxdepth 8 -name '*.rej' 2>/dev/null | wc -l)
if [[ $REJ_COUNT -gt 0 ]]; then
    echo "error: $REJ_COUNT hunks rejected — see *.rej files in src/" >&2
    find "$SRC" -maxdepth 8 -name '*.rej' 2>/dev/null | head -20 >&2
    exit 1
fi

echo "=> overlaying assets/ onto src/ ..."
# `rsync -a` preserves permissions + handles new directories; the trailing
# slash on the source copies CONTENTS, not the assets/ dir itself.
rsync -a "$ROOT/assets/" "$SRC/"

echo
echo "Done. To build:"
echo "    cd src && autoninja -C out/Default chrome"
echo "To launch:"
echo "    bash $ROOT/launch_lean.sh"
