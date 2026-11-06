#!/usr/bin/env python3
"""Seed-based calibration — the review loop's sensitivity measurement
(R57 C4', folding R2/R3/R4: the corpus replays RETENTION mechanically;
seeding measures GENERALIZATION — can a blank-subagent reviewer find
defects that CI cannot?).

Clone-based planting: the defect is applied to a THROWAWAY COPY of the
working tree — the real tree is never contaminated (a forgotten revert is
structurally impossible). The clone itself contains no manifest, but the
sibling manifest file is enumerable by anyone listing the parent
directory; the measurement's validity rests on the reviewer's ignorance
and honesty, not on unreadability.

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


# R59 M-1: the calibration dispatch hygiene, STRUCTURAL at last. A clone
# carrying session artifacts (KICKOFF.md describes the implant protocol —
# a reviewer reading it collapses the calibration) invalidates the seeding.
# Stripping at copy time means a forgotten manual step is structurally
# impossible (2026-11-02 legislation, process-tool layer).
SESSION_ARTIFACTS = (
    "HANDOFF.md", "KICKOFF.md", "loop-progress.log", "ngaf-launch.sh",
    "impl-2026-11-01", ".zcodeignore",
)


def copy_tree(dst: Path):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", ".DS_Store", *SESSION_ARTIFACTS))


def assert_dispatch_hygiene(clone: Path):
    """Loud gate: the clone must NOT contain session artifacts even after
    copy-time stripping (defense in depth — the ignore list is the first
    face, this is the second)."""
    present = [a for a in SESSION_ARTIFACTS if (clone / a).exists()]
    if present:
        raise SystemExit(
            f"seed: DISPATCH HYGIENE VIOLATION — session artifacts leaked into "
            f"the clone: {present}; a calibration reviewer reading them would "
            "collapse the seeding. Refusing to dispatch."
        )


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


def check_anchors():
    """R58 replay face M7: the opening replay gate never exercised the seed
    catalog (planting plus a full clone run per family is too heavy for a
    gate), so a stale injector anchor was silent at round open — the red
    only fired when someone manually ran --verify, if ever. This dry run
    materializes every family's edits exactly as planting would (battery:*
    families via materialize_battery_edit, catalog families as-is) and
    requires every anchor to match the REAL tree exactly once. Zero writes."""
    bad = 0
    for fid, fam in CATALOG.items():
        edits = fam["edits"]
        if edits is None:  # battery family: single-source, same as planting
            edits, _ = materialize_battery_edit(fid)
        ok = True
        for rel, find, _replace in edits:
            f = ROOT / rel
            if not f.exists():
                print(f"{fid}: MISSING FILE {rel} — anchor check impossible (expected 1, found 0)")
                ok = False
                bad += 1
                continue
            n = f.read_text().count(find)
            if n != 1:
                print(f"{fid}: STALE ANCHOR in {rel} — expected 1, found {n} "
                      "(anchor discipline: loud, not silent; update seed.py)")
                ok = False
                bad += 1
        if ok:
            print(f"{fid} → OK ({len(edits)} anchor(s) match exactly once)")
    if bad:
        print(f"seed --check-anchors: {bad} stale/missing anchor(s) — "
              "the catalog is stale, planting would fail")
        return 1
    return 0


def selftest():
    """The hygiene gate's own red faces — synthetic trees, no repo contact:
    A. copy_tree strips every session artifact from the clone
    B. assert_dispatch_hygiene raises loudly on a planted artifact
    """
    failures = []
    tmp = Path(tempfile.mkdtemp(prefix="seed-hygiene-selftest-"))
    try:
        fake_src = tmp / "src"
        fake_src.mkdir()
        for name in ("KICKOFF.md", "HANDOFF.md", "loop-progress.log", "ngaf-launch.sh"):
            (fake_src / name).write_text("session artifact")
        (fake_src / "impl-2026-11-01").mkdir()
        (fake_src / "impl-2026-11-01" / "42-review-meta-analysis-v2.md").write_text("draft")
        (fake_src / "keepme.txt").write_text("real content")
        dst = tmp / "clone"
        # A: stripping face (monkeypatch the module ROOT for this call)
        global ROOT
        saved_root, ROOT = ROOT, fake_src
        try:
            copy_tree(dst)
        finally:
            ROOT = saved_root
        leaked = [a for a in SESSION_ARTIFACTS if (dst / a).exists()]
        if leaked:
            failures.append(f"A: copy_tree leaked session artifacts: {leaked}")
        if not (dst / "keepme.txt").exists():
            failures.append("A: copy_tree stripped non-artifact content (over-broad)")
        # B: hygiene-gate red face
        (dst / "KICKOFF.md").write_text("planted")
        try:
            assert_dispatch_hygiene(dst)
            failures.append("B: hygiene gate did NOT raise on a planted artifact")
        except SystemExit as e:
            if "DISPATCH HYGIENE VIOLATION" not in str(e):
                failures.append(f"B: wrong error surface: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print("SEED SELFTEST FAILURE")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SEED SELFTEST PASS — copy_tree strips session artifacts, "
          "hygiene gate raises on planted artifacts")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--family", help="catalog family id")
    ap.add_argument("--out", help="clone target directory")
    ap.add_argument("--verify", action="store_true", help="prove the expected color, then clean up unless --keep")
    ap.add_argument("--keep", action="store_true", help="keep the clone for reviewer dispatch")
    ap.add_argument("--selftest", action="store_true", help="the hygiene gate's own red faces (synthetic trees)")
    ap.add_argument("--check-anchors", action="store_true",
                    help="dry run: every catalog family's anchors must match the real tree "
                         "exactly once each (zero writes; mutually exclusive with --family/--out)")
    args = ap.parse_args()

    if args.check_anchors:
        if args.family or args.out:
            raise SystemExit("seed: --check-anchors is a dry run and takes no --family/--out")
        return check_anchors()
    if args.selftest:
        return selftest()
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

    manifest_path = out.parent / (out.name + ".seed-manifest.json")
    # R58 M-4: any failure after the clone exists (stale edit anchor, verify
    # red, interrupt) must remove the clone AND the manifest before
    # re-raising the original error. A verify-failure residue left at a
    # fixed path once made every later audit rerun fail with "already
    # exists" — indistinguishable from real token staleness, i.e. the exact
    # failure class the audit exists to catch. The pre-copytree failure
    # (target already exists) has nothing to clean.
    try:
        # R59 m-5: the copy itself is inside the try — a copytree failure
        # (disk full, permission) previously left a PARTIAL clone behind
        # with no cleanup.
        copy_tree(out)
        assert_dispatch_hygiene(out)
        apply_edits(out, edits)
        manifest = {
            "family": args.family,
            "desc": fam["desc"],
            "color": fam["color"],
            "clone": str(out),
            "edits": [{"file": rel, "find": find[:80], "replace": replace[:80]} for rel, find, replace in edits],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f"planted {args.family} -> {out}")
        print(f"manifest (sibling of the clone, enumerable): {manifest_path}")

        if args.verify:
            do_verify(out, fam)
            print(f"verify PASS — expected {fam['color']} reproduced in the clone")
            if not args.keep:
                shutil.rmtree(out)
                manifest_path.unlink()
                print("clone cleaned (use --keep to dispatch a reviewer against it)")
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        manifest_path.unlink(missing_ok=True)
        print(f"seed: verify/edit failed — clone cleaned: {out}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
