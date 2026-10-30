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

HERE = Path(__file__).resolve().parent
ADOPTION_SCHEMA = json.loads((HERE / "adoption.schema.json").read_text())


def load(path: Path):
    """(doc, _expect_match). The fixture's own _expect* keys are read
    permissively (so the suite can assert on them) then popped."""
    doc = json.loads(path.read_text())
    doc.pop("_expect", None)
    match = doc.pop("_expect_match", None)
    return doc, match


def adoption_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(ADOPTION_SCHEMA)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]


def run_suite(valid_dir: Path, invalid_dir: Path) -> int:
    bad = 0
    for f in sorted(valid_dir.glob("*.json")):
        doc, _ = load(f)
        errs = adoption_errors(doc)
        if errs:
            print(f"[adoption] FAIL must-accept {f.name}")
            for e in errs:
                print(f"      {e}")
            bad += 1
        else:
            print(f"[adoption] PASS must-accept {f.name}")
    for f in sorted(invalid_dir.glob("*.json")):
        doc, match = load(f)
        errs = adoption_errors(doc)
        if not errs:
            print(f"[adoption] FAIL must-reject {f.name}  (was accepted!)")
            bad += 1
        elif match and not any(match in e for e in errs):
            print(f"[adoption] FAIL must-reject {f.name}  (rejected for the wrong reason: {errs[0]!r} lacks {match!r})")
            bad += 1
        else:
            print(f"[adoption] PASS must-reject {f.name}  ({errs[0]})")
    return bad


def main() -> int:
    ex = HERE / "examples" / "adoption"
    valid, invalid = ex / "valid", ex / "invalid"
    if not list(valid.glob("*.json")) or not list(invalid.glob("*.json")):
        print("[adoption] suite incomplete: need at least one valid and one invalid example")
        return 1
    bad = run_suite(valid, invalid)
    print(f"[adoption] {len(list(valid.glob('*.json')))} must-accept + "
          f"{len(list(invalid.glob('*.json')))} must-reject, {bad} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
