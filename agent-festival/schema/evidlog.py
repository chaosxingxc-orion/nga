#!/usr/bin/env python3
"""Validate evidlog fixtures (piece 7 spike oracle, Python side)."""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
EVIDLOG_SCHEMA = json.loads((HERE / "evidlog.schema.json").read_text())


def evidlog_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(EVIDLOG_SCHEMA)
    errs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]
    if errs:
        return errs
    # code rule: in-band seq must be dense and increasing (writer-allocated —
    # a gap is a foreign writer or a dropped entry; mirrors the Go checker)
    prev = -1
    for i, e in enumerate(doc["entries"]):
        if e["seq"] != prev + 1:
            errs.append(f"entries/{i}: seq {e['seq']} breaks the dense writer-allocated sequence "
                        f"(want {prev + 1}) — a gap or a foreign writer")
            break
        prev = e["seq"]
    return errs


def main() -> int:
    ex = HERE / "examples" / "evidlog"
    bad = _suite.run_suite("evidlog", ex / "valid", ex / "invalid", evidlog_errors)
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (1, 3):
        print(f"[evidlog] FAIL corpus count {n_valid}+{n_invalid} != pinned 1+3 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
