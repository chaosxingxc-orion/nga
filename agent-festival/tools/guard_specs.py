"""Guard battery spec registry — the C3' repair-time obligation's
registration face.

Every guard constructor following the 件 3' canonical form (see
docs/fixture-guard-pattern.md) MUST register a spec here in the same diff
that introduces it, and MUST pass `python3 tools/guard-battery.py --spec
<name>` before landing. `guard-battery.py --check` is the registry gate:
it scans the repo for `func *Guarded(` declarations and fails on any that
is not registered here (the naming convention is prescribed by the
pattern doc; constructors deliberately deviating from it are a declared
scan blind spot — say so in the pattern doc, don't drift silently).

Spec fields:
  name          registry id (used by --spec)
  file          path relative to the REPO ROOT
  go_dir        the go module directory, relative to the repo root
  pkg           the package pattern for `go test` (relative to go_dir)
  probes        the -run pattern selecting the guard's probe pair
  constructor   the 件 3' constructor's function name
  check_call    the exact call expression inside the guard's if-statement
  default_call  the default-factory call expression
  guard_block   the check-and-return block (must appear exactly once;
                the battery mutates THIS text — anchors are form-bound,
                re-shaping the guard without updating the spec is itself
                a finding)
  param_block   the default-selection block (anchor for ignore_param)
  check_open    the pure check's function opening (anchor for check_gutted)
  consumers     optional list of consumer anchors — [{"file": path relative
                to the REPO ROOT, "pattern": exact string, "count": N}];
                each pattern must occur exactly count times in the named
                real-tree file. This is the M-5 face: the battery mutates
                the constructor, never its call sites, so a caller that
                silently leaves the guarded path is invisible to every
                mutation form — the consumer anchor is the only face that
                sees it. Specs without `consumers` skip the face
                (backward compatible).
"""

SPECS = [
    {
        "name": "e7-canary",
        "file": "agent-festival/go/internal/e2e/e7_canary_test.go",
        "go_dir": "agent-festival/go",
        "pkg": "./internal/e2e",
        "probes": "TestE7b_GuardedPath|TestE7b_GuardChecksProbed",
        "constructor": "canaryMaskingStreamGuarded",
        "check_call": "canaryMaskingFixtureCheck(stream)",
        "default_call": "canaryMaskingStream()",
        "guard_block": (
            "\tif err := canaryMaskingFixtureCheck(stream); err != nil {\n"
            "\t\treturn nil, err\n"
            "\t}\n"
            "\treturn stream, nil\n"
            "}"
        ),
        "param_block": (
            "\tif len(streams) > 0 {\n"
            "\t\tstream = streams[0]\n"
            "\t} else {\n"
            "\t\tstream = canaryMaskingStream()\n"
            "\t}"
        ),
        "check_open": "func canaryMaskingFixtureCheck(stream []ledger.Event) error {",
        # M-5 consumer anchors: both callers of the guarded constructor. If a
        # call site is swapped to bare canaryMaskingStream() (the verified
        # 2026-11-06 bypass: whole e2e package green with both call sites
        # swapped), the mutation battery cannot see it — this face does.
        "consumers": [
            {
                "file": "agent-festival/go/internal/e2e/e7_canary_test.go",
                "pattern": "stream := mustGuardedStream(t)",
                "count": 2,
            },
        ],
    },
]
