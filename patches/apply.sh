#!/usr/bin/env bash
# Apply every fork patch, in series order, from the Chromium source root.
#
#   cd /path/to/chromium/src
#   /path/to/patches/apply.sh [--reverse]
#
# Pass --reverse to unapply (in reverse order).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
series="$here/series"
applyflags=()
order=cat
if [[ "${1:-}" == "--reverse" ]]; then
  applyflags+=(--reverse)
  order=tac
fi

$order "$series" | while read -r p; do
  [[ -z "$p" || "$p" == \#* ]] && continue
  patch="$here/$p"
  # Asset patches (branding/icons.patch, fonts/lean-windows-fonts.patch) carry
  # "Binary files ... differ" markers with no bytes; git apply cannot apply them.
  # Their files are delivered by the assets/ overlay instead — skip them here.
  if grep -q '^Binary files' "$patch"; then
    echo ">> skip (binary assets, supplied by assets/ overlay): $p"
    continue
  fi
  echo ">> git apply ${applyflags[*]:-} $p"
  git apply "${applyflags[@]}" "$patch"
done
