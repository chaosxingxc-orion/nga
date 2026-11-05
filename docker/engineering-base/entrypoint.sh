#!/bin/bash
set -e
# The setup scripts extend PYTHONPATH. Discard caller-supplied values before
# sourcing them: even an absolute path can contain an injected sitecustomize.
unset PYTHONPATH
export CANN_VERSION=9.2.0 ATB_CXX_ABI=1
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source /usr/local/Ascend/cann-${CANN_VERSION}/share/info/ascendnpu-ir/bin/set_env.sh
source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi=${ATB_CXX_ABI:-1}
# Do not inherit paths constructed from caller-controlled environment values.
# These paths are part of the pinned CANN 9.2.0 base image.
export PYTHONPATH=/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B -P /opt/nga/adapter.py "$@"
