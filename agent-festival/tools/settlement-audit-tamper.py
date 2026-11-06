#!/usr/bin/env python3
"""Settlement-audit tamper battery — the audit's own red face.

TestSettlementAudit machine-enforces the settlement-proof protocol. But
"the audit catches violations" is itself a CLAIM, and every claim in this
campaign is mutation-verified or it is an automatic M. This harness is
that claim's proof: it builds synthetic ledgers (via the
SETTLEMENT_AUDIT_LEDGER override, so the real ledger is never touched),
runs the audit against each, and requires:

  violation ledger  → audit RED, with every expected kind reported
                      (presence / grammar / execution×2 / fence)
  control ledger    → audit GREEN (retired skipping, letter form, fence
                      illustration inert, both token shapes passing)

R58 adds three faces to the same contrast pattern (each a minimal ledger,
so a regression turns the face green instead of just changing the kind):
  letter violation  → RED: a scoped entry in letter form (- **M-A**) with
                      no token must trip presence — under the pre-R58
                      numeric-only bullet grammar it passed silently (M-1)
  fence violation   → RED: the only proof inside a fenced block — fence
                      content is documentation; the pre-R58 fence-blind
                      parser false-satisfied the FAIL expectation with the
                      literal <cmd> placeholder (M-2)
  fence-inert control → GREEN: a fenced syntax illustration plus a real
                      bare-line token on a clean ledger — fences must be
                      inert on clean ledgers, and an entry's proof must
                      survive across a fence (M-2)

The synthetic tokens are `echo`/`false`/`exit N` only — no recursion is
possible (the harness never appears in a synthetic ledger), and the inner
audit's execution phase runs them harmlessly.

Exit code 0 iff both detections held.

Tokens in docs/minor-ledger.md invoke this script — a token that cannot
be re-run is not proof (R56 m-3).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GO_DIR = Path(__file__).resolve().parent.parent / "go"
NESTED = "SETTLEMENT_AUDIT_NESTED"
OVERRIDE = "SETTLEMENT_AUDIT_LEDGER"

# Expected violation kinds and entry ids in the violation ledger.
EXPECT_KINDS = ["presence", "grammar", "execution", "fence"]
EXPECT_IDS = ["M-1", "M-2", "M-3", "M-4", "M-6", "M-7"]

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
- **M-6（fence-buried live token）**：settled with a token buried in a
  code fence — invisible to the machine contract, must be loud (R59 B-1).
  ```
  [mutation-proof: echo FAIL → FAIL]
  ```
- **M-7（bare placeholder token）**：settled with a placeholder as the only
  proof — grammar violation (not a token, R61 M-2) AND presence violation
  (no active proof on the entry).
  [mutation-proof: <cmd> → FAIL]
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
- **M-4 (fence-inert control)**: settled with a fenced syntax illustration
  plus a real bare-line token — the fence must be inert on a clean ledger
  (R58 M-2), and the entry's proof must survive across it.
```
[mutation-proof: <reproducible command> → FAIL]
```
  [mutation-proof: exit 3 → FAIL]
"""

# R58 M-1 face: a scoped-section entry in the ledger's letter-id convention
# (R17 M-A/M-B/M-C) with no token must trip presence. Under the pre-R58
# numeric-only bullet grammar this ledger passed the audit silently.
LETTER_VIOLATION_LEDGER = """**settlement-proof protocol (synthetic tamper fixture)**:
every M/B settlement entry from R56 on must embed a mutation-proof token.

## R56 review ledger

- **M-A**: settled in letter form without any proof token.
"""

# R58 M-2 face: the only proof lives inside a fenced block — fence content
# is documentation, never tokens. Under the pre-R58 fence-blind parser the
# fenced line parsed as a live token whose literal <cmd> placeholder failed
# under bash (exit 1) and false-satisfied the FAIL expectation, so this
# ledger passed the audit green.
FENCE_VIOLATION_LEDGER = """**settlement-proof protocol (synthetic tamper fixture)**:
every M/B settlement entry from R56 on must embed a mutation-proof token.

## R56 review ledger

- **M-1**: settled with a proof that lives inside a fence.
```
[mutation-proof: <cmd> → FAIL]
```
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
            if eid == "M-6":
                # R61 M-1: kind-BOUND assertion — the id must appear on a
                # FENCE violation line, not anywhere in the output (a
                # substring check rides on whatever kind happens to mention
                # the entry; the Mut1-class regression — id attachment
                # removed from the parser — must fail HERE).
                if not re.search(r"settlement-audit/fence:.*M-6", out):
                    failures.append("violation ledger: M-6 not reported on a fence violation line (id-level binding)")
            elif eid not in out:
                failures.append(f"violation ledger: expected entry id {eid!r} not reported")

        ctrl_path = tmp / "control-ledger.md"
        ctrl_path.write_text(CONTROL_LEDGER, encoding="utf-8")
        rc, out = run_audit(ctrl_path)
        if rc != 0:
            failures.append(f"control ledger failed the audit (exit {rc}):\n{out[-1500:]}")

        # R58 M-1 face: letter-form entry without a token → presence red
        letter_path = tmp / "letter-violation-ledger.md"
        letter_path.write_text(LETTER_VIOLATION_LEDGER, encoding="utf-8")
        rc, out = run_audit(letter_path)
        if rc == 0:
            failures.append("letter-form violation ledger passed the audit — "
                            "presence is blind to letter-suffix entry ids (M-1)")
        if "settlement-audit/presence" not in out:
            failures.append("letter-form violation ledger: presence kind not reported")
        if "M-A" not in out:
            failures.append("letter-form violation ledger: entry id M-A not reported")

        # R58 M-2 face: fenced-only proof → presence red (fence content is
        # not a token; the literal <cmd> must not false-satisfy FAIL)
        fence_path = tmp / "fence-violation-ledger.md"
        fence_path.write_text(FENCE_VIOLATION_LEDGER, encoding="utf-8")
        rc, out = run_audit(fence_path)
        if rc == 0:
            failures.append("fence violation ledger passed the audit — "
                            "fence content parsed as a live token (M-2)")
        if "settlement-audit/presence" not in out:
            failures.append("fence violation ledger: presence kind not reported")

    if failures:
        print("TAMPER BATTERY FAILURE")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "PASS — violation ledger red (presence/grammar/execution reported, "
        "echo-FAIL and false-OK killed), control ledger green, letter-form "
        "and fenced-only violation faces red, fence-inert control green"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
