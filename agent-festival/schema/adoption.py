#!/usr/bin/env python3
"""Validate adoption-request fixtures (piece 2 oracle, Python side).

An adoption request is a standalone document validated against
adoption.schema.json — there are no cross-request rules at this layer: the
rules that need machine memory (single winner, digest stability per key)
live in go/internal/adopt and are exercised by its Go tests and cmd/adopt
driver. This oracle exists to cross-check the schema itself against a second
validator (jsonschema here, santhosh-tekuri there) — the same
dual-validator discipline the base and the ledger piece use.

Exit 0 iff every examples/adoption/valid/* passes AND every invalid/* is
rejected — and, when an invalid example carries _expect_match, rejected for
that reason.

Usage: python3 schema/adoption.py
Dependencies: jsonschema (pinned in requirements.txt).
"""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
ADOPTION_SCHEMA = json.loads((HERE / "adoption.schema.json").read_text())


def adoption_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(ADOPTION_SCHEMA)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]


def main() -> int:
    ex = HERE / "examples" / "adoption"
    bad = _suite.run_suite("adoption", ex / "valid", ex / "invalid", adoption_errors)
    # D93 count-floor (the Go twin lives in cmd/adopt/main_test.go)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (2, 5):
        print(f"[adoption] FAIL corpus count {n_valid}+{n_invalid} != pinned 2+5 (corpus shrank?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
