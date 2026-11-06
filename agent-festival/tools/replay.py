#!/usr/bin/env python3
"""Red-face replay — the review round's retention gate (R57 C4').

One command re-proves EVERY machine red face the campaign has accumulated.
Run it before dispatching a reviewer (runbook §一.1): a face that went
corrupt shows up here as a table row, not as a surprise mid-round.

  python3 tools/replay.py     # all faces; exit 0 iff every face is green-red as declared

Faces (the inventory lives in docs/attack-corpus.md — the single source):
  M1 registry-gate     unregistered guards / drifted spec anchors /
                       bypassed consumers (M-5)
  M2 battery           ten mutation forms × every registered spec
  M3 battery-selftest  the battery's own six faces
  M4 settlement-audit  every ledger token re-runs to its declared outcome
                       (presence / grammar / execution / staleness) — note
                       M4 internally re-runs M1-M3, M5 and M7 as tokens: the
                       replay is defense-in-depth, not a minimal set
  M5 audit-tamper      the audit's own tamper battery
  M6 audit-selftest    the ledger parser's twelve in-process faces
  M7 seed-anchors      every seed.py catalog anchor matches the real tree
                       exactly once (dry run — catalog staleness is loud at
                       round open, not first-discovered by a failed plant)

This script is ORCHESTRATION — the faces live in the component tools, each
of which carries its own red face and its own ledger token. Replay adds no
new checking; it adds the round gate and one table.
"""

import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
AF_DIR = TOOLS_DIR.parent
GO_DIR = AF_DIR / "go"

FACES = [
    ("M1", "registry-gate", ["python3", "tools/guard-battery.py", "--check"], AF_DIR),
    ("M2", "battery", ["python3", "tools/guard-battery.py"], AF_DIR),
    ("M3", "battery-selftest", ["python3", "tools/guard-battery.py", "--selftest"], AF_DIR),
    ("M4", "settlement-audit", ["go", "test", "./internal/settlement/", "-run", "TestSettlementAudit$", "-count=1"], GO_DIR),
    ("M5", "audit-tamper", ["python3", "tools/settlement-audit-tamper.py"], AF_DIR),
    ("M6", "audit-selftest", ["go", "test", "./internal/settlement/", "-run", "TestSettlementAuditSelfTest", "-count=1"], GO_DIR),
    ("M7", "seed-anchors", ["python3", "tools/seed.py", "--check-anchors"], AF_DIR),
]


def main():
    print(f"{'face':4} {'name':20} verdict")
    print("-" * 44)
    failed = []
    for fid, name, cmd, cwd in FACES:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        ok = proc.returncode == 0
        if not ok:
            failed.append((fid, name, proc.stdout + proc.stderr))
        print(f"{fid:4} {name:20} {'PASS' if ok else 'FAIL'}")
    print("-" * 44)
    if failed:
        print(f"REPLAY: {len(failed)} face(s) FAILED — fix before dispatching a reviewer")
        for fid, name, out in failed:
            print(f"\n=== {fid} {name} ===\n{out[-1200:]}")
        return 1
    print(f"REPLAY: all {len(FACES)} face(s) green — retention proven, round may open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
