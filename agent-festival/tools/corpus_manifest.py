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

def unknown_dirs() -> list[str]:
    """Directories under schema/examples/ that FAMILIES does not know — a
    new fixture family must register here or the 全仓合计 row silently
    stops being a whole-repo count (R14 B-m2: the manifest was blind to
    new sibling directories; --check stayed green with 205 files on disk
    vs 203 in the manifest)."""
    known = set(FAMILIES) | {"valid", "invalid", "envelopes", "keys"}  # family dirs + the base-corpus faces manifest() counts separately
    actual = {d.name for d in Path("schema/examples").iterdir() if d.is_dir()}
    return sorted(actual - known)

def strayed_files() -> list[str]:
    """Every .json under schema/examples/ that the counted faces do NOT
    enumerate (R15 A-1/B-3, the complementary faces of the R14 accident
    family: nested subdirectories under a known family, loose files at any
    level). The family and base rows glob ONE level; a fixture landing
    anywhere else is committed, looks alive, and validates nothing — both
    oracles consume the same single-level globs. The whole-repo row is now
    a true per-file reconciliation: rglob total == enumerated total and
    every file is on an enumerated face."""
    root = Path("schema/examples")
    enumerated: set[Path] = set()
    for fam in FAMILIES:
        base = root / fam
        enumerated.update((base / "valid").glob("*.json"))
        enumerated.update((base / "invalid").glob("*.json"))
    enumerated.update(root.glob("valid/*.json"))
    enumerated.update(root.glob("invalid/*.json"))
    enumerated.update(root.glob("envelopes/**/*.json"))
    enumerated.update(root.glob("keys/**/*.json"))
    actual = set(root.rglob("*.json"))
    return sorted(str(p) for p in actual - enumerated)

def check() -> int:
    doc = DOC.read_text()
    # Delimited parse (R4 m-1): the manifest slot lives between the
    # corpus-manifest comment and the next section header. A stale SECOND
    # block anywhere else — byte-identical or with drifted counts (the probe
    # that beat the previous substring check) — must count as drift too.
    unknown = unknown_dirs()
    if unknown:
        print(f"[manifest] FAIL: unknown fixture directories under schema/examples/ (not in FAMILIES): "
              f"{', '.join(unknown)} — register the family in FAMILIES or the whole-repo row is a lie")
        return 1
    strayed = strayed_files()
    if strayed:
        print(f"[manifest] FAIL: fixture files not on any counted face (nested or loose — the "
              f"single-level globs never see them, both oracles included): {', '.join(strayed)} — "
              f"move the file onto a valid/invalid face or remove it")
        return 1
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
