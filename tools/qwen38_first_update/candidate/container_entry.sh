#!/usr/bin/env bash
set -uo pipefail
out=${FIXTURE_OUT:?}; phase=${FIXTURE_PHASE:?}; work=${FIXTURE_WORK:?}
mkdir -p "$out"
export FIXTURE_STOP_AFTER=0
[[ $phase != phase1 ]] || export FIXTURE_STOP_AFTER=1
heartbeat() { 
  sleeper=
  trap '[[ -z $sleeper ]] || { kill "$sleeper" 2>/dev/null || :; wait "$sleeper" 2>/dev/null || :; }; exit 0' TERM INT
  while :; do printf '%s phase=%s steps=%s\n' "$(date -u +%FT%TZ)" "$phase" "$(grep -h -c '"event": "heartbeat"' "$out"/rank-*.jsonl 2>/dev/null | awk '{s+=$1} END {print s+0}')" >> "$out/heartbeat-$phase.log"; sleep 30 & sleeper=$!; wait "$sleeper" || :; sleeper=; done; }
heartbeat & hb=$!
finalize() {
  rc=$?
  trap - EXIT
  kill "$hb" 2>/dev/null || :
  wait "$hb" 2>/dev/null || :
  printf '%s\n' "$rc" > "$out/exit-$phase.marker" || exit 1
  exit "$rc"
}
trap finalize EXIT
trap 'exit 143' TERM INT
python3 -P "$work/command.py" --output "$out" --phase "$phase" > "$out/command-$phase.txt" 2> "$out/renderer-$phase.stderr"
rc=$?
if (( rc == 0 )); then
  bash "$out/command-$phase.txt" >> "$out/train-$phase.log" 2>&1
  rc=$?
fi
exit "$rc"
