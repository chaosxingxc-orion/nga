#!/usr/bin/env python3
"""Validate event-ledger fixtures (piece 4 oracle).

Ledger documents: JSON Schema + the cross-event rules JSON Schema cannot
express (arbitration_seq monotonicity). Fixtures follow the base's pin
discipline: valid must be accepted, invalid must be rejected for the reason
its _expect_match names.

Exit 0 iff every examples/ledger/valid/* passes AND every invalid/* is
rejected — and, when an invalid example carries _expect_match, rejected for
that reason.

Usage: python3 schema/ledger.py
Dependencies: jsonschema (pinned in requirements.txt).
"""
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
LEDGER_SCHEMA = json.loads((HERE / "event-ledger.schema.json").read_text())


def load(path: Path):
    """(doc, _expect_match). The fixture's own _expect* keys are read
    permissively (so the suite can assert on them) then popped."""
    doc = json.loads(path.read_text())
    doc.pop("_expect", None)
    match = doc.pop("_expect_match", None)
    return doc, match


def ledger_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(LEDGER_SCHEMA)
    errs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]
    if errs:
        return errs
    # cross-event rule: arbitration_seq must be non-decreasing
    seqs = [e["arbitration_seq"] for e in doc["events"]]
    if any(seqs[i] > seqs[i + 1] for i in range(len(seqs) - 1)):
        errs.append(f"events: arbitration_seq must be non-decreasing, got {seqs}")
    # cross-event rule: a payload digest is a function of the operation — the same
    # operation_id across idempotency entries must carry the same digest (15 B4:
    # 'changed payload under the same key' is a rejection, not a second opinion)
    seen: dict[str, str] = {}
    for e in doc["events"]:
        idem = e.get("idempotency")
        if not idem:
            continue
        op, dig = idem["operation_id"], idem["payload_digest"]
        if op in seen and seen[op] != dig:
            errs.append(f"events: operation_id {op!r} carries payload_digest {dig!r} "
                        f"but an earlier event recorded {seen[op]!r} — changed payload under the same key")
        seen[op] = dig
    return errs


def main() -> int:
    ex = HERE / "examples" / "ledger"
    bad = 0
    valid = sorted((ex / "valid").glob("*.json"))
    invalid = sorted((ex / "invalid").glob("*.json"))
    if not valid or not invalid:
        print("[ledger] suite incomplete: need at least one valid and one invalid example")
        return 1
    for f in valid:
        doc, _ = load(f)
        errs = ledger_errors(doc)
        if not errs:
            print(f"[ledger] PASS must-accept {f.name}")
        else:
            print(f"[ledger] FAIL must-accept {f.name}")
            for e in errs:
                print(f"      {e}")
            bad += 1
    for f in invalid:
        doc, match = load(f)
        errs = ledger_errors(doc)
        if not errs:
            print(f"[ledger] FAIL must-reject {f.name}  (was accepted!)")
            bad += 1
        elif match and not any(match in e for e in errs):
            print(f"[ledger] FAIL must-reject {f.name}  (rejected for the wrong reason: {errs[0]!r} lacks {match!r})")
            bad += 1
        else:
            print(f"[ledger] PASS must-reject {f.name}  ({errs[0]})")
    print(f"[ledger] {len(valid)} must-accept + {len(invalid)} must-reject, {bad} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
