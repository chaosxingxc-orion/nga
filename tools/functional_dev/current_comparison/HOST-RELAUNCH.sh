#!/bin/sh
set -eu
src=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/matched-current-dev-consumer-source
out=/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/matched-current-dev-comparison
py=/mnt/cephfs/xingchao/experiments/jev/rc1-host-stage-20261106-2600925-cpu/bin/python
mkdir -p "$out"
cd "$src"
nohup "$py" -B -P "$src/host_runner.py" >> "$out/host-runner.log" 2>&1 < /dev/null &
printf '%s\n' "$!"
