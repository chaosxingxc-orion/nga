#!/bin/bash
set -euo pipefail
attempt="$1"; shift
exec >>"$attempt/run.log" 2>&1
trap 'status=$?; printf "{\"exit_code\":%d,\"utc\":\"%s\"}\n" "$status" "$(date -u +%FT%TZ)" >"$attempt/.EXIT.tmp"; sync "$attempt/.EXIT.tmp"; mv "$attempt/.EXIT.tmp" "$attempt/EXIT.json"' EXIT
# Ascend environment scripts read optional unset shell variables (e.g. ZSH_VERSION).
set +u
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source "/usr/local/Ascend/cann-${CANN_VERSION}/share/info/ascendnpu-ir/bin/set_env.sh"
source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi="${ATB_CXX_ABI:-1}"
set -u
python3 -P /run/package/code/score.py --attempt "$attempt" "$@"
