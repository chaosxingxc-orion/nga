#!/usr/bin/env python3
"""Validate judgment-specification fixtures (piece 3 oracle, Python side).

A judgment specification is a standalone document validated against
judgment.schema.json — every field traces to NGA overall-design §6/§6.1
(no cross-document rules: ownership of semantics belongs to the knowledge
workflow, piece 3's consumer, per the priors). This oracle cross-checks the
schema against the Go twin (go run ./cmd/judgment) — the dual-validator
discipline every growth-layer schema uses.

Exit 0 iff every examples/judgment/valid/* passes AND every invalid/* is
rejected — and, when an invalid example carries _expect_match, rejected for
that reason.

Usage: python3 schema/judgment.py
Dependencies: jsonschema (pinned in requirements.txt).
"""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
JUDGMENT_SCHEMA = json.loads((HERE / "judgment.schema.json").read_text())


def judgment_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(JUDGMENT_SCHEMA)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]


def main() -> int:
    ex = HERE / "examples" / "judgment"
    bad = _suite.run_suite("judgment", ex / "valid", ex / "invalid", judgment_errors)
    # D93 count-floor (the Go twin lives in cmd/judgment/main_test.go)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (2, 6):
        print(f"[judgment] FAIL corpus count {n_valid}+{n_invalid} != pinned 2+6 (corpus shrank?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
