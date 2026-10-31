#!/usr/bin/env python3
"""Validate release-manifest fixtures (piece 5 oracle, Python side).

A release manifest is a standalone document validated against
release.schema.json — every field traces to NGA v0.2 §5 (no cross-document
rules: the linking chain's other links — task recording, promotion,
replay — belong to their consumers; piece 6 reads, never writes). This
oracle cross-checks the schema against the Go twin (go run ./cmd/release).

Exit 0 iff every examples/release/valid/* passes AND every invalid/* is
rejected — and, when an invalid example carries _expect_match, rejected for
that reason.

Usage: python3 schema/release.py
Dependencies: jsonschema (pinned in requirements.txt).
"""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
RELEASE_SCHEMA = json.loads((HERE / "release.schema.json").read_text())


def release_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(RELEASE_SCHEMA)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]


def main() -> int:
    ex = HERE / "examples" / "release"
    bad = _suite.run_suite("release", ex / "valid", ex / "invalid", release_errors)
    # D93 count-floor (the Go twin lives in cmd/release/main_test.go)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (2, 9):
        print(f"[release] FAIL corpus count {n_valid}+{n_invalid} != pinned 2+9 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
