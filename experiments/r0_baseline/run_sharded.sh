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
heartbeat() {
  while true; do
    alive=$(pgrep -fc "run_baseline.py --out-root $out --shard" || true)
    rows=$(for f in "$out"/readouts/*.jsonl; do [ -f "$f" ] && echo "$(basename "$f" | sed 's/__.*//') $(($(wc -l < "$f") - 1))"; done 2>/dev/null \
           | awk '{c[$1]+=$2} END {for (k in c) printf "%s=%d ", k, c[k]}')
    echo "$(date -u +%FT%TZ) alive_shards=$alive rows: $rows" >> "$out/heartbeat.log"
    sleep 60
  done
}
heartbeat & hb=$!
pids=()
for ((i = 0; i < n; i++)); do run_shard "$i" "$@" & pids+=($!); done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done
echo "$(date -u +%FT%TZ) all shards exited, rc=$rc"
if [[ $rc -eq 0 ]]; then
  python3 -P "$here/run_baseline.py" --out-root "$out" --num-shards "$n" --report-only "$@" --device cpu >> "$out/logs/merge.log" 2>&1 || rc=2
fi
kill "$hb" 2>/dev/null
echo "rc=$rc utc=$(date -u +%FT%TZ)" > "$out/$([[ $rc -eq 0 ]] && echo DONE || echo FAILED)"
exit $rc
