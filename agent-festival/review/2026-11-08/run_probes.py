"""Run external contract probes without adding failing tests to the normal suite.

Nonzero is intentionally preserved while system acceptance items remain open.
Use an exact source checkout with LF fixtures; no model or business API is used.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
go_root = here.parents[1] / "go"
go = sys.argv[1] if len(sys.argv) > 1 else "go"
with tempfile.TemporaryDirectory(prefix="nga-contract-review-") as tmp:
    source = Path(tmp) / "review_test.go"
    source.write_bytes((here / "system_contract_probes.go.txt").read_bytes())
    overlay = Path(tmp) / "overlay.json"
    overlay.write_text(json.dumps({"Replace": {
        str(go_root / "internal/e2e/nga_external_review_test.go"): str(source)
    }}), encoding="utf-8")
    result = subprocess.run([
        go, "test", "-overlay=" + str(overlay), "./internal/e2e",
        "-run", "TestNGAReview_|TestP0A|TestXS2", "-count=1", "-v"
    ], cwd=go_root)
    raise SystemExit(result.returncode)
