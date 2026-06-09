#!/usr/bin/env bash
# Apply the canvas-bridge Blink-side patches into a Chromium tree.
#
# Usage:  apply.sh <path-to-chromium/src>
#
# Idempotent: re-running it just re-copies the new files and re-attempts
# the patches (git apply --check first so we don't double-apply).

set -euo pipefail

SRC="${1:?Usage: $0 <chromium-src-root>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -d "$SRC" ]] || [[ ! -f "$SRC/BUILD.gn" ]]; then
  echo "ERROR: $SRC doesn't look like a Chromium src/ tree" >&2
  exit 2
fi

echo "[canvas-bridge] target: $SRC"

# 1. Drop new files into the tree.
install_file() {
  local from="$1" to="$2"
  mkdir -p "$(dirname "$SRC/$to")"
  cp -f "$ROOT/$from" "$SRC/$to"
  echo "  + $to"
}

install_file blink_canvas_bridge/canvas_bridge_switches.h \
    components/canvas_bridge/public/canvas_bridge_switches.h
install_file blink_canvas_bridge/canvas_bridge_switches.cc \
    components/canvas_bridge/canvas_bridge_switches.cc
install_file blink_canvas_bridge/canvas_bridge_codec.h \
    third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.h
install_file blink_canvas_bridge/canvas_bridge_codec.cc \
    third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_codec.cc
install_file blink_canvas_bridge/canvas_bridge_client.h \
    third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_client.h
install_file blink_canvas_bridge/canvas_bridge_client.cc \
    third_party/blink/renderer/platform/canvas_bridge/canvas_bridge_client.cc
install_file blink_canvas_bridge/BUILD.gn \
    third_party/blink/renderer/platform/canvas_bridge/BUILD.gn

# Minimal components/canvas_bridge BUILD.gn so the source_set links.
cat > "$SRC/components/canvas_bridge/BUILD.gn" <<'GN'
# Copyright (c) 2026 Arman Hossain <arman@bytetunnels.com>. ChromiumFish authors.
source_set("canvas_bridge") {
  sources = [
    "canvas_bridge_switches.cc",
    "public/canvas_bridge_switches.h",
  ]
  public_deps = [ "//base" ]
}
GN
echo "  + components/canvas_bridge/BUILD.gn"

# 2. Apply unified diffs to existing files.
shopt -s nullglob
for patch in "$ROOT"/diffs/*.patch; do
  echo "[canvas-bridge] applying $(basename "$patch")"
  if ( cd "$SRC" && git apply --check "$patch" ) 2>/dev/null; then
    ( cd "$SRC" && git apply "$patch" )
  else
    echo "  -> already applied (or doesn't fit current tree); skipping"
  fi
done

echo "[canvas-bridge] done. Rebuild with: autoninja -C out/Default chrome"
