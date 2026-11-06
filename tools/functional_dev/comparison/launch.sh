#!/bin/sh
# Run on 175 after review and staging. A named stopped container is deliberately retained.
set -eu
bundle=${1:?absolute staged bundle directory required}
out=${2:?absolute persistent output directory required}
image=sha256:472672563b30226fbc012c3c15d3d35f2c74dac88775d4970c8fea834d10605d
runtime=/mnt/cephfs/xingchao/experiments/jev/r3_runs/reviewer_torch_runtime_20261101_v1/python/bin/python3.12
mkdir -p "$out"
# Refuse to clobber terminal evidence; removal/renaming is an explicit operator action.
test ! -e "$out/EXIT.json" || { echo 'EXIT.json exists; preserve it and use a new output directory' >&2; exit 1; }
printf '%s\n' "$(date -u +%FT%TZ) launch requested" >> "$out/launch.log"
printf "sh '%s/launch.sh' '%s' '%s'\n" "$bundle" "$bundle" "$out" > "$out/RELAUNCH.sh"
docker run -d --name nga-rc1-dev-comparison --pull never --runtime runc --network none --cpus 2 \
  --mount "type=bind,src=$bundle,dst=/work,readonly" \
  --mount "type=bind,src=$out,dst=/output" \
  --mount type=bind,src=/mnt/cephfs,dst=/mnt/cephfs,readonly \
  --entrypoint /bin/sh "$image" -c '
    set +e
    '"$runtime"' -B /work/watcher.py /work/config.json >> /output/watcher.log 2>&1
    rc=$?
    printf "{\"exit_code\":%s}\n" "$rc" > /output/EXIT.json.tmp
    mv /output/EXIT.json.tmp /output/EXIT.json
    exit "$rc"
  '
