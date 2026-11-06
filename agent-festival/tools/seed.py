#!/usr/bin/env python3
"""Seed-based calibration — the review loop's sensitivity measurement
(R57 C4', folding R2/R3/R4: the corpus replays RETENTION mechanically;
seeding measures GENERALIZATION — can a blank-subagent reviewer find
defects that CI cannot?).

Clone-based planting: the defect is applied to a THROWAWAY COPY of the
working tree — the real tree is never contaminated (a forgotten revert is
structurally impossible). The manifest is written OUTSIDE the clone, so
the reviewer cannot read what was planted.

Two plant classes:
  battery:<form>   a known-family defect (a battery mutation). The clone's
                   probes go RED — machine-detectable. Seeding these tests
                   whether the reviewer runs mechanical checks at all.
  ood-*            out-of-distribution, GREEN-PRESERVING defects: the full
                   suite stays green after planting — only review can find
                   them. These are the generalization probe (M7: plants
                   must not share the reviewer's blind spots, so they come
                   from outside the campaign's own families where possible).

The catalog's injectors are anchored on current file content (anchor
discipline, same as battery/token anchors): an anchor that no longer
matches = --verify RED = update the catalog. Staleness is loud, not
silent.

Usage
-----
  python3 tools/seed.py --list
  python3 tools/seed.py --family <id> --out <dir>            # plant + manifest
  python3 tools/seed.py --family <id> --out <dir> --verify   # plant + prove
                  the expected color (battery: probes RED; ood: suite GREEN
                  under -short) + clean up unless --keep

Detection recording (per docs/attack-corpus.md §植入标定): a ledger section
`## R<N> 标定（植入 a+b，检出 x/y）` — the generalization rate is an
APPROXIMATION (the oracle recursion does not dissolve; distribution-out
does not mean ground truth — declared, not claimed away).
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
AF_DIR = TOOLS_DIR.parent
ROOT = AF_DIR.parent
GO_DIR = AF_DIR / "go"

# ---------------------------------------------------------------------------
# Injectors. Each: (description, expected color, [(file, find, replace)]).
# Anchors are exact-count (must match exactly once per file).

E7 = "agent-festival/go/internal/e2e/e7_canary_test.go"

CATALOG = {
    # --- known family: battery mutants (probes go RED in the clone) ---
    "battery:seventh_early_return": {
        "desc": "known family — the R57 seventh form (early return before the guard call)",
        "color": "RED",
        "verify": ("./internal/e2e/", "TestE7b_GuardedPath|TestE7b_GuardChecksProbed"),
        "edits": None,  # materialized from the battery spec at run time
    },
    # --- out-of-distribution, green-preserving (only review can catch) ---
    "ood-skip-subtest": {
        "desc": "silent coverage loss — one drift form is t.Skip()ed; the suite "
                "stays green while the table quietly stops probing a form",
        "color": "GREEN",
        "verify": (".", None),  # full suite, -short
        "edits": [(E7,
                   "\tfor _, tc := range driftForms {\n\t\tt.Run(tc.name, func(t *testing.T) {",
                   "\tfor _, tc := range driftForms {\n\t\tif tc.name == \"no-death-shape\" {\n\t\t\tt.Skip(\"temporarily disabled\")\n\t\t}\n\t\tt.Run(tc.name, func(t *testing.T) {")],
    },
    "ood-loose-assert": {
        "desc": "silent assertion weakening — the identity projection drops the "
                "Outcome comparison; a drift where seq/type match but the outcome "
                "differs would slip through, and no test goes red",
        "color": "GREEN",
        "verify": (".", None),
        "edits": [(E7,
                   "\t\t\t\tif got[i].ArbitrationSeq != tc.in[i].ArbitrationSeq ||\n"
                   "\t\t\t\t\tgot[i].EventType != tc.in[i].EventType ||\n"
                   "\t\t\t\t\tgot[i].Outcome != tc.in[i].Outcome {",
                   "\t\t\t\tif got[i].ArbitrationSeq != tc.in[i].ArbitrationSeq ||\n"
                   "\t\t\t\t\tgot[i].EventType != tc.in[i].EventType {")],
    },
    "known-doc-drift": {
        "desc": "doc overclaims (known family: 声明失实/熔块 — its machine face does "
                "not exist for prose; review-only): the guard's declared boundary is "
                "silently widened in the godoc",
        "color": "GREEN",
        "verify": (".", None),
        "edits": [(E7,
                   "// Known boundary (declared, not claimed away): a constructor that\n"
                   "// re-implements the five checks inline instead of calling",
                   "// The check is always routed through canaryMaskingFixtureCheck —\n"
                   "// an inline re-implementation cannot occur (instead of calling")],
    },
}


def materialize_battery_edit(family):
    """Known-family plants reuse the battery's own mutants (single source)."""
    sys.path.insert(0, str(TOOLS_DIR))
    from guard_specs import SPECS
    form = family.split(":", 1)[1]
    spec = SPECS[0]  # single-spec registry today; extend when a second guard lands
    import importlib.util
    bspec = importlib.util.spec_from_file_location(
        "guard_battery", TOOLS_DIR / "guard-battery.py")
    guard_battery = importlib.util.module_from_spec(bspec)
    bspec.loader.exec_module(guard_battery)
    anchor, replacement = guard_battery.mutant(spec, form)
    return [(spec["file"], anchor, replacement)], spec


def copy_tree(dst: Path):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", ".DS_Store"))


def apply_edits(clone: Path, edits):
    for rel, find, replace in edits:
        f = clone / rel
        src = f.read_text()
        n = src.count(find)
        if n != 1:
            raise SystemExit(
                f"seed: anchor for {rel} matched {n} times, want 1 — the catalog "
                "is stale (anchor discipline: loud, not silent); update seed.py"
            )
        f.write_text(src.replace(find, replace))


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def do_verify(clone: Path, fam):
    kind, target = fam["verify"]
    if kind == "./internal/e2e/":
        rc, out = run(["go", "test", "./internal/e2e/", "-run", target, "-count=1"], cwd=clone / GO_DIR.relative_to(ROOT))
    else:
        rc, out = run(["go", "test", "./...", "-count=1", "-short"], cwd=clone / GO_DIR.relative_to(ROOT))
    if fam["color"] == "RED" and rc == 0:
        raise SystemExit("seed verify: known-family plant did NOT turn the clone red — "
                         "the plant is inert (catalog or guard changed)")
    if fam["color"] == "GREEN" and rc != 0:
        raise SystemExit(f"seed verify: OOD plant turned the suite red — a plant must be "
                         f"green-preserving (this one is just a bug):\n{out[-1500:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--family", help="catalog family id")
    ap.add_argument("--out", help="clone target directory")
    ap.add_argument("--verify", action="store_true", help="prove the expected color, then clean up unless --keep")
    ap.add_argument("--keep", action="store_true", help="keep the clone for reviewer dispatch")
    args = ap.parse_args()

    if args.list:
        for fid, fam in CATALOG.items():
            print(f"{fid}\t[{fam['color']}] {fam['desc']}")
        return 0
    if not args.family or not args.out:
        raise SystemExit("seed: --family and --out are required (see --list)")

    fam = CATALOG.get(args.family)
    if fam is None:
        raise SystemExit(f"seed: unknown family {args.family!r} (see --list)")

    out = Path(args.out).resolve()
    if out.exists():
        raise SystemExit(f"seed: {out} already exists — pick a fresh target")
    if str(out).startswith(str(ROOT)):
        raise SystemExit("seed: the clone must live OUTSIDE the repo tree")

    edits = fam["edits"]
    if edits is None:  # battery family: single-source the edits
        edits, _ = materialize_battery_edit(args.family)

    copy_tree(out)
    apply_edits(out, edits)
    manifest = {
        "family": args.family,
        "desc": fam["desc"],
        "color": fam["color"],
        "clone": str(out),
        "edits": [{"file": rel, "find": find[:80], "replace": replace[:80]} for rel, find, replace in edits],
    }
    manifest_path = out.parent / (out.name + ".seed-manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"planted {args.family} -> {out}")
    print(f"manifest (OUTSIDE the clone): {manifest_path}")

    if args.verify:
        do_verify(out, fam)
        print(f"verify PASS — expected {fam['color']} reproduced in the clone")
        if not args.keep:
            shutil.rmtree(out)
            manifest_path.unlink()
            print("clone cleaned (use --keep to dispatch a reviewer against it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
