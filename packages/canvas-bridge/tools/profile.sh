#!/usr/bin/env bash
# Resource-usage profile of canvas-bridge-server under load.
#
# Starts the server, samples (RSS, CPU%, threads, file descriptors) at
# 4 Hz while running a sequence of benchmark phases. Prints peak/mean
# resource numbers per phase plus a timeline at the end.

# IMPORTANT: do NOT use `set -e` here — we want the sampler to keep
# going even if a single ps/lsof returns no rows for a tick.
set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER="$ROOT_DIR/target/release/canvas-bridge-server"
BENCH="$SCRIPT_DIR/bench.py"
PY="${PYTHON:-/Users/armansmac2/.local/bin/python3.12}"

PHASES=(
  "idle:--sessions 1 --iters 1 --ops 1"
  "1x100x32:--sessions 1 --iters 100 --ops 32"
  "16x100x32:--sessions 16 --iters 100 --ops 32"
  "64x100x32:--sessions 64 --iters 100 --ops 32"
  "256x100x32:--sessions 256 --iters 100 --ops 32"
  "1024x50x32:--sessions 1024 --iters 50 --ops 32"
  "32x20x64@1024sq:--sessions 32 --iters 20 --ops 64 --width 1024 --height 1024"
  "32x100x256heavy:--sessions 32 --iters 100 --ops 256"
)

TMPDIR="$(mktemp -d -t canvas-bridge-profile.XXXXXX)"
SAMPLE_CSV="$TMPDIR/samples.csv"
> "$SAMPLE_CSV"

cleanup() {
  [[ -n "${SAMPLER_PID:-}" ]] && kill "$SAMPLER_PID" 2>/dev/null
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

now_ms() { "$PY" -c "import time;print(int(time.time()*1000))"; }

echo "[profile] tmp:    $TMPDIR"
echo "[profile] starting server..."
"$SERVER" --listen 127.0.0.1:8443 --auth user:secret >"$TMPDIR/server.log" 2>&1 &
SERVER_PID=$!
sleep 0.5
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "server failed to start; log:" >&2
  cat "$TMPDIR/server.log" >&2
  exit 1
fi
echo "[profile] pid=$SERVER_PID"

# Sampler — explicit script file to avoid subshell issues with `set`.
SAMPLER_SH="$TMPDIR/sampler.sh"
cat > "$SAMPLER_SH" <<EOF
#!/usr/bin/env bash
PID=$SERVER_PID
PY=$PY
OUT=$SAMPLE_CSV
while kill -0 "\$PID" 2>/dev/null; do
  rss=\$(ps -o rss= -p "\$PID" 2>/dev/null | tr -d ' ')
  cpu=\$(ps -o %cpu= -p "\$PID" 2>/dev/null | tr -d ' ')
  # Thread count via 'top' — macOS doesn't expose it in ps -o.
  th=\$(top -l 1 -pid "\$PID" -stats th 2>/dev/null | tail -1 | tr -d ' ')
  fds=\$(lsof -p "\$PID" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
  now=\$("\$PY" -c "import time;print(int(time.time()*1000))")
  printf '%s,%s,%s,%s,%s\n' "\$now" "\${rss:-0}" "\${cpu:-0}" "\${th:-0}" "\${fds:-0}" >> "\$OUT"
  sleep 0.25
done
EOF
chmod +x "$SAMPLER_SH"
"$SAMPLER_SH" &
SAMPLER_PID=$!
sleep 2

baseline=$(tail -1 "$SAMPLE_CSV")
echo "[profile] baseline sample: $baseline   (t_ms,rss_kB,cpu%,threads,fds)"

summarize_window() {
  local start="$1" end="$2"
  awk -F, -v s="$start" -v e="$end" '
    $1 >= s && $1 <= e {
      r = $2 + 0; c = $3 + 0; t = $4 + 0; f = $5 + 0
      if (r > max_rss) max_rss = r
      if (c > max_cpu) max_cpu = c
      if (t > max_th)  max_th  = t
      if (f > max_fd)  max_fd  = f
      sum_cpu += c; n++
    }
    END {
      if (n == 0) { print "  (no samples in window)"; exit }
      printf "  RSS peak: %d kB (%.1f MB)\n", max_rss, max_rss/1024
      printf "  CPU peak: %d%%   mean: %.0f%%   (n=%d)\n", max_cpu, sum_cpu/n, n
      printf "  threads peak: %d\n", max_th
      printf "  fds     peak: %d\n", max_fd
    }
  ' "$SAMPLE_CSV"
}

for phase in "${PHASES[@]}"; do
  tag="${phase%%:*}"
  args="${phase#*:}"
  echo
  echo "============================================================"
  echo "[phase] $tag  →  bench.py $args"
  echo "============================================================"
  start_ms=$(now_ms)
  $PY "$BENCH" $args 2>&1 | grep -E "wall|ops/sec|roundtrips/sec|pixel MB|p50|p90|p99|max|mean"
  end_ms=$(now_ms)
  sleep 0.4  # let sampler land trailing values
  echo "[resource] over $(($end_ms - $start_ms)) ms:"
  summarize_window "$start_ms" "$end_ms"
done

echo
echo "============================================================"
echo "[profile] sampled timeline (every 8th sample)"
echo "          t_rel_s | RSS_MB | CPU% | threads | fds"
awk -F, -v t0="$(head -1 "$SAMPLE_CSV" | cut -d, -f1)" 'NR % 8 == 1 {
  printf "  %5.1fs | %6.1f | %4d | %4d | %4d\n",
    ($1 - t0) / 1000.0, $2/1024, $3+0, $4+0, $5+0
}' "$SAMPLE_CSV"
echo
echo "[profile] CSV saved: $SAMPLE_CSV"
echo "[profile] $(wc -l <"$SAMPLE_CSV" | tr -d ' ') samples"
