#!/usr/bin/env bash
# One run_baseline.py process per NPU inside the container, a heartbeat, a terminal marker, and a merged report.
# Usage (inside the container, code dir mounted at /workspace):
#   bash run_sharded.sh <out_root> <num_shards> [run_baseline.py args ...]
# Process i sees only NPU i (ASCEND_RT_VISIBLE_DEVICES=i) and is shard i of num_shards. A shard that dies is retried
# up to 3 times (the harness resumes at item level, so a retry loses at most one chunk).
# Outputs in <out_root>: logs/shardN.log, run.log (this script), heartbeat.log (one line per minute: UTC time,
# readout rows per scorer, shards alive), and the terminal marker DONE or FAILED (content: exit code + UTC time).
# The marker, not the container state, says whether the run finished.
# python3 -P, not -I: -I drops PYTHONPATH and CANN's tbe is found only through it.
set -uo pipefail
out=$1; n=$2; shift 2
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$out/logs"
rm -f "$out/DONE" "$out/FAILED"
# Declare the watch tier for tools/watchdog.py: a scoring pass over the frozen data runs for hours
# and heartbeats once a minute, so it belongs in the slow tier. Without this file the watchdog has
# to infer a stall threshold from the heartbeat period. Override with WATCH_TIER=fast|medium|slow.
# WATCH_TOTAL is the number of readout rows the run intends to write, which the launcher knows and
# the watchdog cannot infer; declaring it turns the digest's bare row count into a fraction and an
# estimated finish. A wrong value is loud rather than silent (TOTAL EXCEEDED / UNREACHABLE).
printf '{"tier": "%s"%s}\n' "${WATCH_TIER:-slow}" "${WATCH_TOTAL:+, \"total\": $WATCH_TOTAL}" > "$out/WATCH.json"
exec >> "$out/run.log" 2>&1
echo "$(date -u +%FT%TZ) start out=$out shards=$n args: $*"

run_shard() {   # $1 = shard index
  local i=$1 try rc=1; shift
  for try in 1 2 3; do
    ASCEND_RT_VISIBLE_DEVICES=$i python3 -P "$here/run_baseline.py" --out-root "$out" --shard "$i" --num-shards "$n" \
      --device npu "$@" >> "$out/logs/shard$i.log" 2>&1 && return 0
    rc=$?; echo "$(date -u +%FT%TZ) shard $i attempt $try exited rc=$rc"
  done
  return $rc
}
heartbeat() {   # $@ = the shard job PIDs to watch
  local pids=("$@") p alive
  while true; do
    # Count live shard jobs by PID, not by pattern. A pattern match over the command line
    # double-counts, because each shard's python process spawns a child that inherits its
    # cmdline, which reported 16 alive for 8 shards and would have hidden a dead shard.
    alive=0
    for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=$((alive + 1)); done
    rows=$(for f in "$out"/readouts/*.jsonl; do [ -f "$f" ] && echo "$(basename "$f" | sed 's/__.*//') $(($(wc -l < "$f") - 1))"; done 2>/dev/null \
           | awk '{c[$1]+=$2} END {for (k in c) printf "%s=%d ", k, c[k]}')
    echo "$(date -u +%FT%TZ) alive_shards=$alive/${#pids[@]} rows: $rows" >> "$out/heartbeat.log"
    sleep 60
  done
}
pids=()
for ((i = 0; i < n; i++)); do run_shard "$i" "$@" & pids+=($!); done
heartbeat "${pids[@]}" & hb=$!
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done
echo "$(date -u +%FT%TZ) all shards exited, rc=$rc"
if [[ $rc -eq 0 ]]; then
  python3 -P "$here/run_baseline.py" --out-root "$out" --num-shards "$n" --report-only "$@" --device cpu >> "$out/logs/merge.log" 2>&1 || rc=2
fi
kill "$hb" 2>/dev/null
echo "rc=$rc utc=$(date -u +%FT%TZ)" > "$out/$([[ $rc -eq 0 ]] && echo DONE || echo FAILED)"
exit $rc
