#!/usr/bin/env python3
"""Guard mutation battery — spec-driven (R57 C3': the repair-time
obligation's machine face).

Why this exists
---------------
R57 C1' replaced form-enumerating pins with an error-returning guard
constructor plus a form-independent probe pair. But "the probe pair
catches every re-shape" is itself a CLAIM — every claim in this campaign
is mutation-verified or it is an automatic M. This script is that claim's
proof, generalized (C3'): ANY guard following the 件 3' canonical form
 registers a spec in guard_specs.py and runs this battery — the
repair-time obligation "the replacement passes the battery before
landing" becomes one command.

Modes
-----
  python3 tools/guard-battery.py                  # all specs × all forms
  python3 tools/guard-battery.py --spec e7-canary # one spec
  python3 tools/guard-battery.py --only seventh   # one form, all specs
  python3 tools/guard-battery.py --check          # registry gate: every
                  # `func *Guarded(` constructor in the repo must have a
                  # spec; every spec's anchors must appear exactly once
  python3 tools/guard-battery.py --selftest       # the battery's own red
                  # faces (registry catches unregistered/misanchored;
                  # battery catches a compile-broken mutant as BROKEN,
                  # never as red)

Exit code 0 iff every applied mutation turned the probes red (test-red,
not compile-red — a mutant that does not compile is MUTANT-BROKEN, a
battery failure) and the baseline is green. The baseline has two steps
(R58): `go vet` on the mutated package first (a registry text anchor
cannot see dead guard code — the seventh form's text anchors PASS on
unreachable code, vet flags it in ~1s), then the probe baseline.

R58 M-3: the battery runs ENTIRELY INSIDE A THROWAWAY COPY of the module
directory. The real target file is only ever READ; the real tree is never
written. There is nothing to restore and no `git checkout` recovery to
need, and a concurrent settlement-audit copy or seed.py clone can no
longer capture a mutated tree — the old in-place mutation window is
structurally gone, not merely shortened.

The tokens in docs/minor-ledger.md invoke this script — a token that
cannot be re-run is not proof (R56 m-3).
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from guard_specs import SPECS  # noqa: E402

ROOT = TOOLS_DIR.parent.parent  # repo root (tools/ -> agent-festival/ -> root)

# ---------------------------------------------------------------------------
# Mutation forms. Each mutant is derived from the spec's canonical blocks —
# the 件 3' body shape prescribes the variable name `stream` (pattern doc);
# a spec deviating from it produces non-compiling mutants, which the
# compile-check reports as MUTANT-BROKEN instead of silently counting as
# "caught" (methodology 76: compile-red is not test-red).

MUTATION_ORDER = [
    "drop_call", "body_noop", "discard_result", "swallow_error",
    "if_false_burial", "seventh_early_return", "ignore_param",
    "hardcoded_nil", "hardcoded_err", "check_gutted", "mutate_after_check",
]

MUTATION_DOC = {
    "drop_call": "delete the guard call (R56 M-A)",
    "body_noop": "call the guard but ignore its result (R56 M-B)",
    "discard_result": "discard the check result (re-route form)",
    "swallow_error": "keep the if-block, swallow the error on the error path",
    "if_false_burial": "bury the guard in `if false` (constant-folded dead code)",
    "seventh_early_return": "early `return` BEFORE the guard — the R57 seventh form",
    "ignore_param": "ignore the caller's stream, always validate the default (R56 M-1)",
    "hardcoded_nil": "always return nil error (check bypassed wholesale)",
    "hardcoded_err": "always return an error (the ACCEPT face must go red)",
    "check_gutted": "gut the pure check itself (check layer == path layer oracle)",
    # R61: the R58 carried clause — check passes, then the returned stream
    # is MUTATED in transit (check-then-swap). Spec-neutral (generic slice
    # operation — no type literals), so the fake module compiles it too.
    "mutate_after_check": "return a MUTATED stream after the check passed (the accept face's identity assertion is the only red face)",
}


def mutant(spec, name):
    """Return (anchor_text, replacement_text) for a mutation form."""
    gb, pb, co = spec["guard_block"], spec["param_block"], spec["check_open"]
    chk = spec["check_call"]
    if name == "drop_call":
        return gb, "\treturn stream, nil\n}"
    if name == "body_noop":
        return gb, "\t_ = %s\n\treturn stream, nil\n}" % chk.split("(")[0]
    if name == "discard_result":
        return gb, "\t_ = stream\n\treturn stream, nil\n}"
    if name == "swallow_error":
        return gb, "\tif err := %s; err != nil {\n\t\t_ = err\n\t}\n\treturn stream, nil\n}" % chk
    if name == "if_false_burial":
        inner = gb.rstrip("}").rstrip("\n")
        return gb, "\tif false {\n" + inner.replace("\n", "\n\t") + "\n\t}\n\treturn stream, nil\n}"
    if name == "seventh_early_return":
        return gb, "\treturn stream, nil\n" + gb
    if name == "ignore_param":
        return pb, "\t_ = streams\n\tstream = %s" % spec["default_call"]
    if name == "hardcoded_nil":
        return gb, "\t_ = %s\n\treturn stream, nil\n}" % chk
    if name == "hardcoded_err":
        return gb, "\t_ = %s\n\treturn nil, fmt.Errorf(\"always\")\n}" % chk
    if name == "check_gutted":
        return co, co + "\n\tif true {\n\t\treturn nil\n\t}"
    if name == "mutate_after_check":
        return gb, """\tif err := %s; err != nil {
\t\treturn nil, err
\t}
\tif len(stream) > 0 {
\t\tstream = stream[:len(stream)-1]
\t}
\treturn stream, nil
}""" % chk
    raise SystemExit(f"battery: unknown mutation {name!r}")


def apply_mutation(src, spec, name):
    anchor, replacement = mutant(spec, name)
    n = src.count(anchor)
    if n != 1:
        raise SystemExit(
            f"battery: anchor for {name!r} matched {n} times, want 1 — "
            "the guard was re-shaped without updating its spec (that is "
            "itself a finding: the battery's anchors are form-bound)"
        )
    return src.replace(anchor, replacement)


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode == 0, proc.stdout + proc.stderr


def compiles(go_dir, pkg):
    """Zero-test compile check: `go test -run '^$'` compiles and runs nothing.
    A mutant failing HERE is MUTANT-BROKEN — never count it as red."""
    ok, _ = run(["go", "test", pkg, "-run", "^$", "-count=1"], cwd=go_dir)
    return ok


def run_probes(go_dir, pkg, probes):
    return run(["go", "test", pkg, "-run", probes, "-count=1"], cwd=go_dir)


def battery_one(spec, only=None):
    """Run the battery for one spec — entirely inside a throwaway copy of
    the module dir (R58 M-3): the real target file is only ever READ, every
    mutation/compile/probe runs against the copy, so a concurrent audit
    copy or seed clone can never capture a mutated tree. Returns
    (exit_code, lines)."""
    root = spec.get("_root", ROOT)
    module_src = root / spec["go_dir"]
    rel_target = Path(spec["file"]).relative_to(spec["go_dir"])
    pkg, probes = spec["pkg"], spec["probes"]
    names = [only] if only else MUTATION_ORDER
    lines = []
    failures = []

    original = (root / spec["file"]).read_text()
    with tempfile.TemporaryDirectory(prefix="guard-battery-run-") as td:
        work = Path(td) / "module"
        shutil.copytree(module_src, work)
        target = work / rel_target

        # R58 vet clause (baseline step 1, also on --only runs): the
        # registry's text anchors pass even on dead guard code, while vet
        # flags unreachable/dead code in ~1s — a vet-dirty module is
        # baseline-red before any mutation runs.
        green, out = run(["go", "vet", pkg], cwd=work)
        if not green:
            print(f"BASELINE IS RED (vet) for spec {spec['name']} — fix the tree first")
            print(out[-2000:])
            return 2, lines
        green, out = run_probes(work, pkg, probes)
        if not green:
            print(f"BASELINE IS RED for spec {spec['name']} — fix the tree first")
            print(out[-2000:])
            return 2, lines
        print(f"spec {spec['name']} ({spec['file']}):")
        print(f"  {'mutation':24} {'probes':8} verdict")
        print("  " + "-" * 50)
        for name in names:
            target.write_text(apply_mutation(original, spec, name))
            try:
                if not compiles(work, pkg):
                    failures.append(name)
                    lines.append(f"  {name:24} {'BROKEN':8} MUTANT-BROKEN — compile-red is not test-red (76)")
                    continue
                ok, out = run_probes(work, pkg, probes)
            finally:
                target.write_text(original)
            red_count = out.count("--- FAIL")
            if ok:
                failures.append(name)
                lines.append(f"  {name:24} {'GREEN':8} BATTERY FAILURE — mutation survived")
            else:
                lines.append(f"  {name:24} {'FAIL':8} red ({red_count} subtest(s))")
        print("  " + "-" * 50)

    if failures:
        lines.append(f"  FAIL — {len(failures)} mutation(s) survived/broken: {failures}")
        return 1, lines
    lines.append(f"  PASS — all {len(names)} mutation(s) turned the probes red")
    return 0, lines


# ---------------------------------------------------------------------------
# Registry gate (--check) and its self-test faces.

GUARD_DECL_RE = re.compile(r"(?m)^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*Guarded)\(")
NON_TEST_PREFIXES = ("Test", "Benchmark", "Example", "Fuzz")


def check_registry(root, specs):
    """Every `func *Guarded(` declaration must be registered; every spec's
    anchors must appear exactly once in its file; every spec that declares
    `consumers` must find each consumer pattern exactly `count` times in
    the real tree (M-5: the battery mutates the constructor, never its call
    sites — consumer anchors are the only face watching a caller bypass).
    Returns gap list."""
    gaps = []
    registered = {(s["file"], s["constructor"]) for s in specs}
    for gof in sorted(root.rglob("*.go")):
        rel = str(gof.relative_to(root))
        if "/.git/" in rel or rel.startswith(".git/"):
            continue
        try:
            src = gof.read_text()
        except OSError:
            continue
        for m in GUARD_DECL_RE.finditer(src):
            name = m.group(1)
            if name.startswith(NON_TEST_PREFIXES):
                continue
            if (rel, name) not in registered:
                gaps.append(f"UNREGISTERED GUARD: {rel}: {name} — register it in "
                            f"tools/guard_specs.py and run the battery (C3' obligation)")
    for s in specs:
        f = root / s["file"]
        if not f.exists():
            gaps.append(f"SPEC {s['name']}: file missing: {s['file']}")
            continue
        src = f.read_text()
        if f"func {s['constructor']}(" not in src and f"func ({s['constructor']}(" not in src:
            gaps.append(f"SPEC {s['name']}: constructor {s['constructor']} not declared in {s['file']}")
        for key in ("guard_block", "param_block", "check_open"):
            n = src.count(s[key])
            if n != 1:
                gaps.append(f"SPEC {s['name']}: {key} matched {n} times, want 1 — "
                            "the guard was re-shaped without updating its spec")
        for c in s.get("consumers", []):
            cf = root / c["file"]
            if not cf.exists():
                gaps.append(f"SPEC {s['name']}: consumer file missing: {c['file']}")
                continue
            n = cf.read_text().count(c["pattern"])
            if n != c["count"]:
                gaps.append(
                    f"SPEC {s['name']}: CONSUMER DRIFT in {c['file']}: pattern "
                    f"{c['pattern']!r} found {n} time(s), want {c['count']} — a caller "
                    "left the guarded path (the battery mutates the constructor only; "
                    "consumer anchors are the only face that sees a bypassed call site)")
    return gaps


def selftest():
    """The battery's own red faces — synthetic trees, no repo contact:
    A. an unregistered `*Guarded(` constructor is caught by --check
    B. a registered spec with a drifted anchor is caught by --check
    C. a well-formed fake guard passes --check AND the full battery
    D. a compile-broken mutant is reported MUTANT-BROKEN, never as red
    E. a caller bypassing the guarded constructor (consumer count drift)
       is caught by --check; a matching consumer anchor passes (M-5)
    F. a module that compiles but fails `go vet` (unreachable code) is
       baseline-red (exit 2) before any mutation runs (R58 vet clause)
    """
    tmp = Path(tempfile.mkdtemp(prefix="guard-battery-selftest-"))
    try:
        return _selftest_body(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # R59 m-4: selftest dirs leaked (26 found in TMPDIR)


def _selftest_body(tmp):
    failures = []
    fake_pkg = tmp / "fake"
    fake_pkg.mkdir()
    (fake_pkg / "go.mod").write_text("module fakeguard\n\ngo 1.24\n")
    (fake_pkg / "fake_test.go").write_text('''package fake

import (
	"errors"
	"fmt"
	"testing"
)

var _ = fmt.Sprint // the hardcoded_err mutant uses fmt.Errorf; the import must exist at baseline

func theDefault() []int { return []int{1} }

func checkFake(stream []int) error {
	if len(stream) == 0 {
		return errors.New("empty")
	}
	return nil
}

func fakeGuarded(streams ...[]int) ([]int, error) {
	var stream []int
	if len(streams) > 0 {
		stream = streams[0]
	} else {
		stream = theDefault()
	}
	if err := checkFake(stream); err != nil {
		return nil, err
	}
	return stream, nil
}

func TestFakeGuardedPath(t *testing.T) {
	if _, err := fakeGuarded([]int{}); err == nil {
		t.Fatal("accepted an empty stream")
	}
	got, err := fakeGuarded()
	if err != nil {
		t.Fatalf("rejected the default: %v", err)
	}
	def := theDefault()
	if len(got) != len(def) || got[0] != def[0] {
		t.Fatalf("default-path identity violated: got %v, want %v (R61: the check-then-mutate return face's red carrier)", got, def)
	}
}
''')
    base_spec = {
        "name": "fake",
        "file": "fake/fake_test.go",
        "go_dir": "fake",
        "pkg": ".",
        "probes": "TestFakeGuardedPath",
        "constructor": "fakeGuarded",
        "check_call": "checkFake(stream)",
        "default_call": "theDefault()",
        "guard_block": "\tif err := checkFake(stream); err != nil {\n\t\treturn nil, err\n\t}\n\treturn stream, nil\n}",
        "param_block": "\tif len(streams) > 0 {\n\t\tstream = streams[0]\n\t} else {\n\t\tstream = theDefault()\n\t}",
        "check_open": "func checkFake(stream []int) error {",
        "_root": tmp,
    }

    # A: unregistered guard detected
    gaps = check_registry(tmp, [])
    if not any("fakeGuarded" in g for g in gaps):
        failures.append(f"A: unregistered fakeGuarded not detected: {gaps}")

    # B: drifted anchor detected
    drifted = dict(base_spec, guard_block="\tif err := checkFake(stream); err != nil {\n\t\treturn BOGUS\n\t}\n\treturn stream, nil\n}")
    gaps = check_registry(tmp, [drifted])
    if not any("guard_block" in g for g in gaps):
        failures.append(f"B: drifted anchor not detected: {gaps}")

    # C: well-formed spec passes the check AND the battery
    gaps = check_registry(tmp, [base_spec])
    if gaps:
        failures.append(f"C: well-formed spec flagged: {gaps}")
    rc, lines = battery_one(base_spec)
    if rc != 0:
        failures.append(f"C: battery on well-formed fake failed (rc={rc}):\n" + "\n".join(lines))

    # D: compile-broken mutant reported BROKEN, never red
    broken = dict(base_spec, default_call="undefinedDefault()")
    rc, lines = battery_one(broken, only="ignore_param")
    if rc == 0:
        failures.append("D: compile-broken mutant did not fail the battery")
    if not any("MUTANT-BROKEN" in l for l in lines):
        failures.append(f"D: broken mutant not reported as MUTANT-BROKEN:\n" + "\n".join(lines))
    if any(re.search(r"FAIL\s+red \(", l) for l in lines):
        failures.append("D: broken mutant was counted as red — compile-red leaked into the verdict")

    # E: consumer drift — a caller swapping the guarded constructor for the
    # bare one — is caught by --check; a matching consumer anchor passes.
    # The battery mutates the constructor only, so this is the M-5 face.
    match_consumer = dict(base_spec, consumers=[
        {"file": "fake/fake_test.go", "pattern": "func fakeGuarded(", "count": 1},
    ])
    gaps = check_registry(tmp, [match_consumer])
    if gaps:
        failures.append(f"E: matching consumer anchor flagged: {gaps}")
    drifted_consumer = dict(base_spec, consumers=[
        {"file": "fake/fake_test.go", "pattern": "stream := mustGuardedStream(t)", "count": 1},
    ])
    gaps = check_registry(tmp, [drifted_consumer])
    if not any("CONSUMER DRIFT" in g and "found 0 time(s), want 1" in g for g in gaps):
        failures.append(f"E: consumer drift not detected with expected/found counts: {gaps}")

    # F: the vet-baseline clause — a module that compiles but fails `go vet`
    # (unreachable code here) is baseline-red (exit 2) before any mutation.
    vet_pkg = tmp / "vetred"
    vet_pkg.mkdir()
    (vet_pkg / "go.mod").write_text("module vetred\n\ngo 1.24\n")
    (vet_pkg / "vetred.go").write_text(
        "package vetred\n\nfunc f() int {\n\treturn 1\n\treturn 2\n}\n")
    vet_spec = {
        "name": "vetred", "file": "vetred/vetred.go", "go_dir": "vetred",
        "pkg": ".", "probes": "TestNothing",
        "constructor": "unused", "check_call": "unused", "default_call": "unused",
        "guard_block": "", "param_block": "", "check_open": "",
        "_root": tmp,
    }
    try:
        rc_vet, _ = battery_one(vet_spec)
    except SystemExit as e:  # e.g. vet unexpectedly green -> mutation anchors fire
        rc_vet = f"SystemExit({e})"
    if rc_vet != 2:
        failures.append(f"F: vet-dirty module did not produce baseline-red exit 2 (got {rc_vet})")

    print("\n".join(lines) if lines else "(selftest silent)")
    if failures:
        print("SELFTEST FAILURE")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SELFTEST PASS — registry catches unregistered/misanchored/bypassed-consumer, "
          "broken mutants are BROKEN not red, well-formed passes, vet-dirty is baseline-red")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="run a single spec by name")
    ap.add_argument("--only", help="run a single mutation form (all specs)")
    ap.add_argument("--check", action="store_true", help="registry gate only (no mutations)")
    ap.add_argument("--selftest", action="store_true", help="the battery's own red faces")
    ap.add_argument("--list", action="store_true", help="list specs and forms")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.check:
        gaps = check_registry(ROOT, SPECS)
        if gaps:
            print("REGISTRY GATE: FAIL")
            for g in gaps:
                print(f"  - {g}")
            return 1
        print(f"REGISTRY GATE: PASS — {len(SPECS)} spec(s) anchored, no unregistered guards")
        return 0
    if args.list:
        for s in SPECS:
            print(f"{s['name']}\t{s['file']}\t{s['constructor']}")
        print("--")
        for name in MUTATION_ORDER:
            print(f"{name}\t{MUTATION_DOC[name]}")
        return 0

    specs = SPECS
    if args.spec:
        specs = [s for s in SPECS if s["name"] == args.spec]
        if not specs:
            raise SystemExit(f"battery: unknown spec {args.spec!r}")
    overall = 0
    for s in specs:
        rc, lines = battery_one(s, only=args.only)
        print("\n".join(lines))
        overall = overall or rc
    return overall


if __name__ == "__main__":
    sys.exit(main())
