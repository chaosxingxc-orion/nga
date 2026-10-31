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
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]


def main() -> int:
    ex = HERE / "examples" / "replay"
    bad = _suite.run_suite("replay", ex / "valid", ex / "invalid", replay_errors)
    # D93 count-floor (the Go twin lives in cmd/replay/main_test.go)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (7, 3):
        print(f"[replay] FAIL corpus count {n_valid}+{n_invalid} != pinned 7+3 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
