#!/usr/bin/env bash
# Inside the container: bash run_check.sh <out_dir> <source> [extra check_scorer.py args]. Writes <out_dir>/DONE_<source> with the exit code.
out=$1; src=$2; shift 2
mkdir -p "$out/$src"
python3 -P "$(dirname "$0")/check_scorer.py" --source "$src" --out-dir "$out" "$@" >> "$out/$src/run.log" 2>&1
rc=$?
echo "rc=$rc utc=$(date -u +%FT%TZ)" > "$out/DONE_$src"
exit $rc
