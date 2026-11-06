#!/usr/bin/env python3
"""Guard mutation battery — the connection-layer red face's own regression suite.

Why this exists
---------------
R57 C1' replaced form-enumerating pins (text/AST pins) with an
error-returning guard constructor plus a form-independent probe pair
(TestE7b_GuardedPathRejectsDrift / TestE7b_GuardedPathAcceptsHealthy).
A pin enumerates shapes and shapes are an OPEN SET — the R57 "seventh
form" (an early `return` before the guard call leaves every pinned
substring intact while the guard becomes dead code) defeated six text
pins at once. The probe pair closes that by observing one semantic value
(does a drifted stream come back as an error?).

But "the probe pair catches every re-shape" is itself a CLAIM — and every
claim in this campaign is mutation-verified or it is an automatic M. So
this script is the probe pair's own battery: it applies each known
degeneration to the guard constructor in place, runs the probes, and
requires every mutation to turn them RED.

Usage
-----
    python3 tools/guard-battery.py                 # all mutations
    python3 tools/guard-battery.py --only seventh  # a single mutation
    python3 tools/guard-battery.py --list          # names only

Exit code 0 iff every applied mutation turned the probes red AND the
baseline is green. The source file is restored on every exit path; if the
script is killed hard, `git checkout -- <file>` recovers it.

The tokens in docs/minor-ledger.md invoke this script — a token that
cannot be re-run is not proof (R56 m-3).
"""

import argparse
import subprocess
import sys
from pathlib import Path

GO_DIR = Path(__file__).resolve().parent.parent / "go"
TARGET = GO_DIR / "internal" / "e2e" / "e7_canary_test.go"
PROBE_RUN = "TestE7b_GuardedPath|TestE7b_GuardChecksProbed"

# The guarded constructor's check-and-return block, as it must appear.
GUARD_BLOCK = """	if err := canaryMaskingFixtureCheck(stream); err != nil {
		return nil, err
	}
	return stream, nil
}"""

PARAM_BLOCK = """	if len(streams) > 0 {
		stream = streams[0]
	} else {
		stream = canaryMaskingStream()
	}"""

MUTATIONS = {
    # name: (description, replacement)
    "drop_call": (
        "delete the guard call (R56 M-A)",
        "\treturn stream, nil\n}",
    ),
    "body_noop": (
        "call the guard but ignore its result (R56 M-B / R54 M-2 re-route)",
        "\t_ = canaryMaskingFixtureCheck\n\treturn stream, nil\n}",
    ),
    "discard_result": (
        "discard the check result explicitly (R56 re-route form)",
        "\t_ = stream\n\treturn stream, nil\n}",
    ),
    "swallow_error": (
        "keep the if-block but swallow the error on the error path",
        """	if err := canaryMaskingFixtureCheck(stream); err != nil {
		_ = err
	}
	return stream, nil
}""",
    ),
    "if_false_burial": (
        "bury the guard in an `if false` block (constant-folded dead code)",
        """	if false {
		if err := canaryMaskingFixtureCheck(stream); err != nil {
			return nil, err
		}
	}
	return stream, nil
}""",
    ),
    "seventh_early_return": (
        "early `return` BEFORE the guard call — THE R57 SEVENTH FORM: every "
        "text/AST pin stays satisfiable, the guard is dead code",
        "\treturn stream, nil\n" + GUARD_BLOCK,
    ),
    "ignore_param": (
        "ignore the caller's stream, always validate the default fixture "
        "(R56 M-1: the tautology this class started as)",
        "\t_ = streams\n\tstream = canaryMaskingStream()",
    ),
    "hardcoded_nil": (
        "always return nil error (the check is bypassed wholesale)",
        '\t_ = canaryMaskingFixtureCheck(stream)\n\treturn stream, nil\n}',
    ),
    "hardcoded_err": (
        "always return an error (the ACCEPT face must go red)",
        '\t_ = canaryMaskingFixtureCheck(stream)\n\treturn nil, fmt.Errorf("always")\n}',
    ),
    "check_gutted": (
        "gut the PURE check itself — the check layer and the path layer share "
        "one oracle, so both the meta probe and the path probes must go red",
        "func canaryMaskingFixtureCheck(stream []ledger.Event) error {\n\tif true {\n\t\treturn nil\n\t}",
    ),
}

# Replacement targets are parameterised: the block mutations replace
# GUARD_BLOCK, the parameter mutation replaces PARAM_BLOCK, and
# check_gutted replaces the check's function opening.
BLOCK_SCOPED = {
    "drop_call", "body_noop", "discard_result", "swallow_error",
    "if_false_burial", "seventh_early_return", "hardcoded_nil",
    "hardcoded_err",
}

CHECK_ANCHOR = "func canaryMaskingFixtureCheck(stream []ledger.Event) error {"


def run_probes():
    proc = subprocess.run(
        ["go", "test", "./internal/e2e/", "-run", PROBE_RUN, "-count=1"],
        cwd=GO_DIR,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, proc.stdout + proc.stderr


def apply_mutation(src, name):
    desc, replacement = MUTATIONS[name]
    if name == "check_gutted":
        anchor = CHECK_ANCHOR
    elif name in BLOCK_SCOPED:
        anchor = GUARD_BLOCK
    else:
        anchor = PARAM_BLOCK
    if src.count(anchor) != 1:
        raise SystemExit(
            f"battery: anchor for {name!r} matched {src.count(anchor)} times, want 1 — "
            "the guard constructor was re-shaped without updating this battery "
            "(that is itself a finding: the battery's anchors are form-bound)"
        )
    return src.replace(anchor, replacement)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single mutation by name")
    ap.add_argument("--list", action="store_true", help="list mutation names")
    args = ap.parse_args()

    if args.list:
        for name, (desc, _) in MUTATIONS.items():
            print(f"{name}\t{desc}")
        return 0

    names = [args.only] if args.only else list(MUTATIONS)
    unknown = [n for n in names if n not in MUTATIONS]
    if unknown:
        raise SystemExit(f"battery: unknown mutation(s): {unknown}")

    original = TARGET.read_text()
    failures = []
    try:
        green, out = run_probes()
        if not green:
            print("BASELINE IS RED — fix the tree before running the battery")
            print(out[-2000:])
            return 2
        print(f"{'mutation':24} {'probes':8} verdict")
        print("-" * 52)

        for name in names:
            TARGET.write_text(apply_mutation(original, name))
            try:
                ok, out = run_probes()
            finally:
                TARGET.write_text(original)
            red_count = out.count("--- FAIL")
            if ok:
                failures.append(name)
                print(f"{name:24} {'GREEN':8} BATTERY FAILURE — mutation survived")
            else:
                print(f"{name:24} {'FAIL':8} red ({red_count} subtest(s))")
    finally:
        TARGET.write_text(original)

    print("-" * 52)
    if failures:
        print(f"FAIL — {len(failures)} mutation(s) survived: {failures}")
        return 1
    print(f"PASS — all {len(names)} mutation(s) turned the probes red")
    return 0


if __name__ == "__main__":
    sys.exit(main())
