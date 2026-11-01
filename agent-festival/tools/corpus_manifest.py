#!/usr/bin/env python3
"""Regenerate the corpus manifest in docs/conformance-fixture-format.md.

The hand-maintained table above explains the corpus; THIS manifest is the
machine-generated one (pi's config-schemas precedent: derived counts, CI
can diff). Run after any corpus change:
    python3 tools/corpus_manifest.py   # prints the manifest block
The block is delimited by the corpus-manifest comment — replace its content
between the comment and the next section header.
"""
import json
from pathlib import Path

FAMILIES = ["ledger", "adoption", "judgment", "release", "replay", "compose", "evidlog"]

def _count(pattern: str) -> int:
    return len(list(Path("schema/examples").glob(pattern)))

def manifest() -> str:
    lines = []
    total = 0
    for fam in FAMILIES:
        base = Path("schema/examples") / fam
        v = len(list((base / "valid").glob("*.json")))
        i = len(list((base / "invalid").glob("*.json")))
        lines.append(f"| `{fam}` | {v} + {i} |")
        total += v + i
    lines.append(f"| 增长族合计 | {total} |")
    base_total = _count("valid/*.json") + _count("invalid/*.json") + _count("envelopes/**/*.json")
    lines.append(f"| 基座契约/信封 | {base_total} |")
    all_total = total + base_total + _count("keys/**/*.json")
    lines.append(f"| 全仓合计（含密钥库） | {all_total} |")
    return "\n".join(lines)

if __name__ == "__main__":
    print(manifest())
