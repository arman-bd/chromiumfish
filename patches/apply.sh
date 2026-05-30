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
  [[ -z "$p" ]] && continue
  echo ">> git apply ${applyflags[*]:-} $p"
  git apply "${applyflags[@]}" "$here/$p"
done
