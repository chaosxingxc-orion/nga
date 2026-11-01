#!/usr/bin/env python3
"""Regenerate (or verify) the corpus manifest in docs/conformance-fixture-format.md.

The hand-maintained table above explains the corpus; THIS manifest is the
machine-generated one (pi's config-schemas precedent: derived counts, CI
can diff). Run after any corpus change:
    python3 tools/corpus_manifest.py            # prints the manifest block
    python3 tools/corpus_manifest.py --check    # diff the committed block, rc=1 on drift
The block is delimited by the corpus-manifest comment — replace its content
between the comment and the next section header. --check is the mechanical
gate: the committed block was hand-edited once (R2 M2 — duplicate rows with
drifted labels) and nothing caught it; --check must stay green on HEAD.
"""
import sys
from pathlib import Path

DOC = Path("docs/conformance-fixture-format.md")
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

def check() -> int:
    doc = DOC.read_text()
    if manifest() not in doc:
        print(f"[manifest] FAIL: the block in {DOC} does not match the regenerated "
              f"manifest — hand-edited rows or a corpus change without a re-render. "
              f"Fix: python3 tools/corpus_manifest.py > (paste between the "
              f"corpus-manifest comment and the next section header).")
        return 1
    print(f"[manifest] OK: committed block == regenerated manifest ({DOC})")
    return 0

if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        sys.exit(check())
    print(manifest())
