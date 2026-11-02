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
import re
import sys
from pathlib import Path

DOC = Path("docs/conformance-fixture-format.md")
FAMILIES = ["ledger", "adoption", "judgment", "release", "replay", "compose", "evidlog"]

def _count(pattern: str) -> int:
    return len(list(Path("schema/examples").glob(pattern)))

def manifest() -> str:
    # The header rows belong to the machine too (R4 m-1: delimited --check
    # exposed that the old generator skipped them — the slot's first two rows
    # were silently hand-maintained while the block claimed do-not-edit).
    lines = ["| 族 | valid + invalid |", "|---|---|"]
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
    # Delimited parse (R4 m-1): the manifest slot lives between the
    # corpus-manifest comment and the next section header. A stale SECOND
    # block anywhere else — byte-identical or with drifted counts (the probe
    # that beat the previous substring check) — must count as drift too.
    m = re.search(r"<!-- corpus-manifest:.*?-->\n(.*?)(?=\n## )", doc, re.S)
    if not m:
        print(f"[manifest] FAIL: no corpus-manifest block found in {DOC} — "
              f"the delimited slot (comment → next ## header) is missing.")
        return 1
    if m.group(1).strip() != manifest():
        print(f"[manifest] FAIL: the delimited block in {DOC} does not match the "
              f"regenerated manifest — hand-edited rows or a corpus change "
              f"without a re-render. Fix: python3 tools/corpus_manifest.py > "
              f"(paste between the corpus-manifest comment and the next "
              f"section header).")
        return 1
    # Sentinel count, not full-block count: a stale second block with DRIFTED
    # counts or OLD-STYLE LABELS (R5 F4 probe — "| 增长族合计（非密钥库）|"
    # beat the exact-label sentinel) never equals manifest(), but every
    # manifest-shaped table starts some total row with the generator's 增长族
    # label prefix — a second occurrence is a duplicate, equal or not.
    n = len(re.findall(r"^\| 增长族合计[^\n]*$", doc, re.M))
    if n > 1:
        print(f"[manifest] FAIL: {n} manifest-shaped tables in {DOC} (sentinel "
              f"增长族合计 seen {n} times) — a duplicate/stale block exists "
              f"outside the slot; keep exactly one.")
        return 1
    print(f"[manifest] OK: committed block == regenerated manifest ({DOC})")
    return 0

if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        sys.exit(check())
    print(manifest())
