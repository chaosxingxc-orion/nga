#!/usr/bin/env python3
"""Validate replay-case fixtures (piece 6 oracle, Python side — FORMAT ONLY).

Per the collision ruling (E): the Python oracle drives ONLY from the
machine-readable replay-case.schema.json (schema-as-source). Any behavioral
judgment on the Python side would be a second implementation of the replay
engine smuggling in through the format layer — the behavior face is Go
单侧 (internal/replay drives the production state machine; see the piece-6
priors' honest-boundary ruling).

Usage: python3 schema/replay.py
"""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
REPLAY_SCHEMA = json.loads((HERE / "replay-case.schema.json").read_text())


def replay_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(REPLAY_SCHEMA)
    errs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]
    if errs:
        return errs
    # 数值域章程 v2 literal gate (R16 A-M1): divergence_at is a business
    # number — JSON Schema's integer type accepts 3.0 by value, the Go typed
    # view rejects the literal; this rule makes both sides reject the same
    # documents (json.loads yields float exactly for float syntax).
    exp = doc.get("expected") or {}
    da = exp.get("divergence_at")
    if isinstance(da, float):
        errs.append(f"[REPLAY.SEQ_FLOAT_SYNTAX] expected.divergence_at {da!r} is not an integer literal — "
                    f"the divergence locator domain is integer; this package does no "
                    f"float math (user ruling 2026-11-02)")
    elif isinstance(da, int) and da > 2 ** 63 - 1:
        # bignum beyond int64: Go's typed view rejects it — the twin arm
        # keeps the dual oracles on the same verdict (family form, ledger
        # seq-int64-overflow precedent)
        errs.append(f"[REPLAY.SEQ_INT64_OVERFLOW] expected.divergence_at {da} exceeds the int64 domain — "
                    f"the divergence locator domain; such a case is not machine-writable")
    return errs


def main() -> int:
    ex = HERE / "examples" / "replay"
    bad = _suite.run_suite("replay", ex / "valid", ex / "invalid", replay_errors)
    # D93 count-floor (the Go twin lives in cmd/replay/main_test.go)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (8, 9):
        print(f"[replay] FAIL corpus count {n_valid}+{n_invalid} != pinned 8+9 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
