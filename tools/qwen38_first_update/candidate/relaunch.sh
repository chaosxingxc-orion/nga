#!/usr/bin/env bash
# Invoke on the NPU host after main review, from a persistent copied candidate directory.
set -euo pipefail
: "${FIXTURE_WORK:?absolute persistent candidate directory}" "${FIXTURE_OUT:?absolute persistent output directory}" "${NAME:?unique retained container name}" "${NPUS:?four physical device IDs}" "${FIXTURE_PHASE:?phase1, resume, or continuous}"
[[ $FIXTURE_PHASE =~ ^(phase1|resume|continuous)$ ]]
read -ra cards <<< "${NPUS//,/ }"
[[ ${#cards[@]} == 4 ]]
mkdir -p "$FIXTURE_OUT"
[[ ! -e $FIXTURE_OUT/exit-$FIXTURE_PHASE.marker ]] || { echo 'phase marker exists; use a fresh output or phase' >&2; exit 1; }
args=(-d --name "$NAME" --network host --shm-size 64g --ulimit memlock=-1:-1 --ulimit stack=67108864:67108864 -v /mnt/cephfs:/mnt/cephfs -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc)
for d in "${cards[@]}"; do args+=(--device "/dev/davinci$d"); done
for p in /usr/local/sbin /etc/ascend_install.info; do [[ ! -e $p ]] || args+=(-v "$p:$p:ro"); done
args+=(-e ASCEND_RT_VISIBLE_DEVICES=0,1,2,3 -e "FIXTURE_OUT=$FIXTURE_OUT" -e "FIXTURE_WORK=$FIXTURE_WORK" -e "FIXTURE_PHASE=$FIXTURE_PHASE" -e 'PYTHONPATH=/mnt/cephfs/xingchao/docker/verl_v030_20261029/site:/mnt/cephfs/xingchao/docker/verl_v030_20261029/src/verl' -e PYTHONSAFEPATH=1 -e TRANSFORMERS_OFFLINE=1 -e HF_HUB_OFFLINE=1)
image=sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7
printf '%q ' env "FIXTURE_WORK=$FIXTURE_WORK" "FIXTURE_OUT=$FIXTURE_OUT" "FIXTURE_PHASE=$FIXTURE_PHASE" "NAME=$NAME" "NPUS=$NPUS" bash "$FIXTURE_WORK/relaunch.sh" > "$FIXTURE_OUT/relaunch-$FIXTURE_PHASE.txt"
printf '\n' >> "$FIXTURE_OUT/relaunch-$FIXTURE_PHASE.txt"
docker run "${args[@]}" "$image" bash "$FIXTURE_WORK/container_entry.sh"
