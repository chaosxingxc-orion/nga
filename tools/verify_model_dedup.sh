#!/bin/bash
# Verify that each model directory present under BOTH cephfs mirror roots has byte-identical MODEL
# CONTENT, so the redundant copy can be removed safely. Matching file names and sizes are not enough
# to delete on.
#
# Excludes `.complete`, which is provenance, not content: it holds the revision hash AND the local
# download timestamp, so two correct copies of the same revision differ in it. A first version of
# this script hashed it and reported all 9 models DIFFERENT, which was an artifact of this script,
# not a difference in the weights. The revision line is compared separately and must match.
#
# Writes per-file hash lists and a per-model verdict, then a terminal marker DONE holding the exit
# code (CLAUDE.md section 7: the marker, not process state, is the truth).
set -u
R=/mnt/cephfs/xingchao
A=$R/models/jev           # the unified root, which the pre-registration names
B=$R/omni/models/jev      # the project-directory root being emptied
OUT=$R/experiments/jev/dedup_models_verify
mkdir -p "$OUT/lists"
: > "$OUT/result.txt"
: > "$OUT/heartbeat.log"
rc=0
for m in $(ls "$B"); do
  if [ ! -d "$A/$m" ]; then
    echo "MISSING_IN_A $m" >> "$OUT/result.txt"; rc=1; continue
  fi
  # Revision line of the provenance file, compared on its own.
  ra=$(head -1 "$A/$m/.complete" 2>/dev/null || echo NONE)
  rb=$(head -1 "$B/$m/.complete" 2>/dev/null || echo NONE)
  # Per-file hashes of everything except the provenance file.
  (cd "$A/$m" && find . -type f ! -name '.complete' | sort | xargs sha256sum) > "$OUT/lists/$m.a" 2>/dev/null
  (cd "$B/$m" && find . -type f ! -name '.complete' | sort | xargs sha256sum) > "$OUT/lists/$m.b" 2>/dev/null
  nd=$(diff "$OUT/lists/$m.a" "$OUT/lists/$m.b" | grep -c '^[<>]' || true)
  nf=$(wc -l < "$OUT/lists/$m.a")
  if [ "$ra" != "$rb" ]; then
    v=REV_DIFF; rc=1
  elif [ "$nd" -eq 0 ]; then
    v=IDENTICAL
  else
    v=DIFFERENT; rc=1
  fi
  echo "$v $m files=$nf differing_lines=$nd rev=${ra:0:12}" >> "$OUT/result.txt"
  echo "$(date -u +%FT%TZ) checked=$m verdict=$v" >> "$OUT/heartbeat.log"
done
echo "rc=$rc utc=$(date -u +%FT%TZ)" > "$OUT/DONE"
exit $rc
