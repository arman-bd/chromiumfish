#!/usr/bin/env bash
# Apply the ChromiumFish fork on top of a vanilla Chromium checkout.
#
# Usage from the root of this repo (where src/ does NOT yet exist):
#
#   1. Follow https://chromium.googlesource.com/chromium/src/+/main/docs/mac_build_instructions.md
#      to get depot_tools and check out Chromium into ./src.
#   2. Sync to the exact commit this fork is authored against — Chromium
#      149.0.7827.115 (the value in UPSTREAM_REVISION):
#         (cd src && git checkout "$(cat ../UPSTREAM_REVISION)")
#         gclient sync --with_branch_heads --reset
#   3. Run this script.
#
# What it does:
#   * Applies every source patch listed in patches/series (one file per
#     feature), in order, SKIPPING the two binary-placeholder patches
#     (branding/icons.patch, fonts/lean-windows-fonts.patch) whose bytes are
#     delivered by the assets/ overlay rather than by patch hunks.
#   * Overlays assets/* on top of src/* (icons, fonts, and other binary /
#     generated files that don't compress well as patch hunks).
#   * Leaves all other source files untouched.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src"

if [[ ! -d "$SRC" ]]; then
    echo "error: $SRC/ not found. Check out Chromium first (see top of this file)." >&2
    exit 1
fi

UPSTREAM_REV="$(cat "$ROOT/UPSTREAM_REVISION")"
CURRENT_REV="$(git -C "$SRC" rev-parse HEAD)"
if [[ "$CURRENT_REV" != "$UPSTREAM_REV" ]]; then
    echo "warning: src/ is at $CURRENT_REV but this fork is authored against" >&2
    echo "         $UPSTREAM_REV (Chromium 149.0.7827.115). Patches may need" >&2
    echo "         manual fixup at hunks that drifted upstream." >&2
fi

echo "=> applying source patches from patches/series ..."
while IFS= read -r p; do
    # skip blank lines and comments in the series file
    [[ -z "$p" || "$p" == \#* ]] && continue
    patch="$ROOT/patches/$p"
    if [[ ! -f "$patch" ]]; then
        echo "error: patch listed in series but missing: $p" >&2
        exit 1
    fi
    # Skip asset patches (branding/icons.patch, fonts/lean-windows-fonts.patch):
    # they carry "Binary files ... differ" markers with no bytes (and, for icons,
    # one co-located .xpm text hunk). Every file they touch is delivered wholesale
    # by the assets/ overlay below, so applying them here is impossible and moot.
    if grep -q '^Binary files' "$patch"; then
        echo "   skip (binary assets, supplied by assets/ overlay): $p"
        continue
    fi
    echo "   apply: $p"
    if ! git -C "$SRC" apply --whitespace=fix "$patch"; then
        echo "error: failed to apply $p" >&2
        echo "       src/ must be a clean checkout of $UPSTREAM_REV" >&2
        echo "       (Chromium 149.0.7827.115) for the series to apply cleanly." >&2
        exit 1
    fi
done < "$ROOT/patches/series"

echo "=> overlaying assets/ onto src/ (icons, fonts, binary/generated files) ..."
# `rsync -a` preserves permissions + handles new directories; the trailing
# slash on the source copies CONTENTS, not the assets/ dir itself.
rsync -a "$ROOT/assets/" "$SRC/"

echo
echo "Done. To build:"
echo "    cd src && autoninja -C out/Default chrome"
