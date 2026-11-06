#!/usr/bin/env python3
"""Settlement-audit tamper battery — the audit's own red face.

TestSettlementAudit machine-enforces the settlement-proof protocol. But
"the audit catches violations" is itself a CLAIM, and every claim in this
campaign is mutation-verified or it is an automatic M. This harness is
that claim's proof: it builds synthetic ledgers (via the
SETTLEMENT_AUDIT_LEDGER override, so the real ledger is never touched),
runs the audit against each, and requires:

  violation ledger  → audit RED, with every expected kind reported
                      (presence / grammar / execution×2)
  control ledger    → audit GREEN (retired skipping + both token shapes
                      passing)

The synthetic tokens are `echo`/`false`/`exit N` only — no recursion is
possible (the harness never appears in a synthetic ledger), and the inner
audit's execution phase runs them harmlessly.

Exit code 0 iff both detections held.

Tokens in docs/minor-ledger.md invoke this script — a token that cannot
be re-run is not proof (R56 m-3).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

GO_DIR = Path(__file__).resolve().parent.parent / "go"
NESTED = "SETTLEMENT_AUDIT_NESTED"
OVERRIDE = "SETTLEMENT_AUDIT_LEDGER"

# Expected violation kinds and entry ids in the violation ledger.
EXPECT_KINDS = ["presence", "grammar", "execution"]
EXPECT_IDS = ["M-1", "M-2", "M-3", "M-4"]

VIOLATION_LEDGER = """**清偿证明协议（synthetic tamper fixture）**：
从 R56 起每条 M/B 清偿的台账条目必须内嵌突变命令 token。

## R56 复审记账

- **M-1（presence miss）**：settled without any proof token.
- **M-2（echo fake）**：settled with a fake token.
  [mutation-proof: echo FAIL → FAIL]
- **M-3（false OK）**：settled with a fake token.
  [mutation-proof: false → OK]
- **M-4（grammar drift）**：settled with a narrative expectation.
  [mutation-proof: echo hi → 输出含 FAIL]
- **M-5（retired token）**：settled; the retired line is skipped, the
  active successor carries the proof.
  [mutation-proof: false → FAIL] [retired-by: deadbeef superseded by the battery]
  [mutation-proof: exit 3 → FAIL]
"""

CONTROL_LEDGER = """**清偿证明协议（synthetic control fixture）**：
从 R56 起每条 M/B 清偿的台账条目必须内嵌突变命令 token。

## R56 复审记账

- **M-1（control FAIL）**：settled with a real failing command.
  [mutation-proof: exit 3 → FAIL]
- **M-2（control OK）**：settled with a succeeding verifier.
  [mutation-proof: true → OK]
- **M-3（retired only, superseded）**：settled.
  [mutation-proof: false → FAIL] [retired-by: deadbeef superseded]
  [mutation-proof: true → OK]
"""


def run_audit(ledger_path: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k != NESTED}
    env[OVERRIDE] = str(ledger_path)
    proc = subprocess.run(
        ["go", "test", "./internal/settlement/", "-run", "TestSettlementAudit$", "-count=1"],
        cwd=GO_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        viol_path = tmp / "violation-ledger.md"
        viol_path.write_text(VIOLATION_LEDGER, encoding="utf-8")
        rc, out = run_audit(viol_path)
        if rc == 0:
            failures.append("violation ledger passed the audit — detection failed")
        for kind in EXPECT_KINDS:
            if f"settlement-audit/{kind}" not in out:
                failures.append(f"violation ledger: expected kind {kind!r} not reported")
        for eid in EXPECT_IDS:
            if eid not in out:
                failures.append(f"violation ledger: expected entry id {eid!r} not reported")

        ctrl_path = tmp / "control-ledger.md"
        ctrl_path.write_text(CONTROL_LEDGER, encoding="utf-8")
        rc, out = run_audit(ctrl_path)
        if rc != 0:
            failures.append(f"control ledger failed the audit (exit {rc}):\n{out[-1500:]}")

    if failures:
        print("TAMPER BATTERY FAILURE")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "PASS — violation ledger red (presence/grammar/execution reported, "
        "echo-FAIL and false-OK killed), control ledger green"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
