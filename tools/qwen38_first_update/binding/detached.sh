#!/usr/bin/env bash
# Run as a detached, persistent host process; OUT/attempt must be on durable shared storage.
set -u
attempt=${1:?absolute prepared attempt path}
python3 -P "$attempt/fixture.py" run --attempt "$attempt" >> "$attempt/controller.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$attempt/controller-exit.marker.tmp"
mv "$attempt/controller-exit.marker.tmp" "$attempt/controller-exit.marker"
exit "$rc"
