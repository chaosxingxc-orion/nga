#!/usr/bin/env bash
# Run from any directory. Use this interpreter for both installation and tests.
set -euo pipefail
nga_python="${NGA_LOCAL_PYTHON:-python3}"
nga_tools="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
nga_install_scope=()
if "$nga_python" -c 'import sys; sys.exit(0 if sys.prefix == sys.base_prefix else 1)'; then
  nga_install_scope=(--user)
fi
"$nga_python" -m pip install "${nga_install_scope[@]}" -r "$nga_tools/requirements-local-cpu.txt"
"$nga_python" - <<'PY'
import importlib.metadata
import json
import sys
import numpy
import scipy
import jsonschema
import pytest
import torch

assert numpy.isfinite(numpy.array([1.0])).all()
assert torch.tensor([1.0, 2.0]).sum().item() == 3.0
print(json.dumps({"python": sys.executable, "packages": {
    name: importlib.metadata.version(name)
    for name in ("numpy", "scipy", "jsonschema", "pytest", "torch")
}}, indent=2))
PY
