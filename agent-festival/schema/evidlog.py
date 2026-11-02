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
    # code rule: seq must be an integer LITERAL (user ruling 2026-11-02:
    # this package does no float math — the counter domain is machine-written
    # int64; json.loads yields float exactly for float-syntax literals, so
    # isinstance int == literal check; mirrors Go's json.Number.Int64
    # rejection — the old ±2^53 sub-domain charter retired with the
    # normalization)
    for i, e in enumerate(doc["entries"]):
        if isinstance(e["seq"], float):
            errs.append(f"[EVIDLOG.SEQ_FLOAT_SYNTAX] entries/{i}: seq {e['seq']!r} is not an integer literal — "
                        f"the counter domain is machine-written int64; this package does no "
                        f"float math (user ruling 2026-11-02)")
            return errs
        if isinstance(e["seq"], int) and (e["seq"] > 2 ** 63 - 1 or e["seq"] < -(2 ** 63)):
            errs.append(f"[EVIDLOG.SEQ_INT64_OVERFLOW] entries/{i}: seq {e['seq']} exceeds the int64 domain — "
                        f"the writer's counter domain; such a document is not machine-writable")
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
    # D93 count-floor (the Go twin lives in cmd/evidlog/main_test.go — R13
    # A-m4: this was the one family pair missing the cross-reference).
    if (n_valid, n_invalid) != (1, 6):
        print(f"[evidlog] FAIL corpus count {n_valid}+{n_invalid} != pinned 1+6 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
