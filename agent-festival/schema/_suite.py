"""Shared fixture-suite harness for the Python oracles (NOT an oracle itself).

Mirrors go/internal/suite: valid must be accepted, invalid must be rejected —
and, when an invalid fixture pins a reason via _expect_match, rejected for
that reason. Pin loading follows the base's hardened semantics: a
wrong-typed _expect_match fails LOUD (V28 F-1 — a silent downgrade to "no
pin" would bypass the wrong-reason checks; the Go twin enforces the same),
and a fixture whose JSON failed to parse is rejected-at-parse with its pin
still matchable against the parse error (V32 M-1's two-path split).

The oracles (ledger.py, adoption.py, judgment.py, release.py, replay.py, compose.py, evidlog.py) stay
deliberately independent in their CHECKERS — that is the dual-validator cross-check —
but the harness around them is not a checked semantic, so it is shared
(R2 m-3: the two inline runners had to be edited in lockstep).
"""
import json
import re
from pathlib import Path

_PIN_RE = re.compile(r'"_expect_match"\s*:\s*"([^"]*)"')


def load(path: Path):
    """(doc, expect_match, error). See load_extras — this is the
    single-extra (wrong-reason pin) face of it."""
    doc, match, _, err = load_extras(path)
    return doc, match, err


def load_extras(path: Path, extra_keys: tuple = ()):
    """(doc, expect_match, extras, error).

    The hardened loader every oracle family rides (R19 B-M1: compose now
    rides it too — its inline loader never received the V28 F-1
    wrong-typed-pin LOUD semantics). extra_keys pop additional pinned
    faces (e.g. compose's _expect_composed) with the SAME hardening:
    a wrong-typed extra fails loud instead of downgrading to "absent".

    error is either a parse failure (doc is None; the pin, if any, is still
    best-effort extracted from the raw text — the base's LoadFixture does the
    same) or a wrong-typed pin (the doc parsed; the suite FAILs loud instead
    of running unpinned).
    """
    raw = path.read_text()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        m = _PIN_RE.search(raw)
        return None, (m.group(1) if m else None), {}, f"document rejected at parse: {e}"
    doc.pop("_expect", None)  # descriptive only
    match = doc.pop("_expect_match", None)
    if match is not None and not isinstance(match, str):
        return doc, None, {}, f"_expect_match must be a string, got {type(match).__name__}"
    extras = {}
    for k in extra_keys:
        v = doc.pop(k, None)
        if v is not None and not isinstance(v, dict):
            return doc, None, {}, f"{k} must be an object, got {type(v).__name__}"
        if v is not None:
            extras[k] = v
    return doc, match, extras, None


def run_suite(label: str, valid_dir: Path, invalid_dir: Path, errors) -> int:
    """Run the two-phase suite; returns the failure count (0 = green)."""
    valid = sorted(valid_dir.glob("*.json"))
    invalid = sorted(invalid_dir.glob("*.json"))
    if not valid or not invalid:
        print(f"[{label}] suite incomplete: need at least one valid and one invalid example")
        return 1
    bad = 0
    for f in valid:
        doc, _, err = load(f)
        if doc is None or err:
            print(f"[{label}] FAIL must-accept {f.name}  ({err})")
            bad += 1
            continue
        errs = errors(doc)
        if errs:
            print(f"[{label}] FAIL must-accept {f.name}")
            for e in errs:
                print(f"      {e}")
            bad += 1
        else:
            print(f"[{label}] PASS must-accept {f.name}")
    for f in invalid:
        doc, match, err = load(f)
        name = f.name
        if doc is not None and err:
            # the DOCUMENT parsed; the error is a malformed pin. An unreadable
            # pin cannot verify the rejection and must not MASK the
            # was-accepted verdict (V32 M-1).
            print(f"[{label}] FAIL must-reject {name}  ({err} — an unreadable pin cannot verify the rejection)")
            bad += 1
            continue
        errs = [err] if doc is None else errors(doc)
        if not errs:
            print(f"[{label}] FAIL must-reject {name}  (was accepted!)")
            bad += 1
        elif match and not any(match in e for e in errs):
            print(f"[{label}] FAIL must-reject {name}  (rejected for the wrong reason: {errs[0]!r} lacks {match!r})")
            bad += 1
        else:
            print(f"[{label}] PASS must-reject {name}  ({errs[0]})")
    print(f"[{label}] {len(valid)} must-accept + {len(invalid)} must-reject, {bad} failures")
    return bad


def main(label: str, valid_dir: Path, invalid_dir: Path, errors) -> int:
    bad = run_suite(label, valid_dir, invalid_dir, errors)
    return 1 if bad else 0


def _self_test() -> bool:
    """Pin the V28/V32 hardening arms (R17 m-3): wrong-typed pins fail LOUD
    and parse-failed pins stay armed — the Go twin has seven poison tests;
    without this, the Python half of the hardening is dead code no oracle
    ever exercises."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        valid = Path(tmp) / "valid"
        invalid = Path(tmp) / "invalid"
        valid.mkdir()
        invalid.mkdir()
        (valid / "ok.json").write_text('{"_expect": "clean"}')
        # wrong-typed pin on the must-reject side: loud FAIL, not a silent
        # downgrade to "no pin"
        bad = invalid / "bad-pin.json"
        bad.write_text('{"poison": "x", "_expect_match": 5}')
        captured = _capture(lambda: run_suite("t", valid, invalid, lambda d: ["poison"] if "poison" in d else []))
        if "FAIL must-reject bad-pin.json" not in captured or "_expect_match must be a string" not in captured:
            print("[_suite] SELF-TEST FAIL: wrong-typed pin not loud")
            ok = False
        # parse-failed fixture with a NON-matching pin: the wrong-reason
        # check must stay armed against the parse error
        unparseable = invalid / "unparseable.json"
        unparseable.write_text('{"poison": "unterminated", "_expect_match": "zzz"}')
        captured = _capture(lambda: run_suite("t", valid, invalid, lambda d: ["poison"] if "poison" in d else []))
        if "rejected for the wrong reason" not in captured:
            print("[_suite] SELF-TEST FAIL: parse-failed pin disarmed")
            ok = False
    return ok


def _capture(f) -> str:
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        f()
    return buf.getvalue()


if __name__ == "__main__":
    # the hardening self-test: python3 schema/_suite.py --self-test
    import sys
    if "--self-test" in sys.argv:
        ok = _self_test()
        print("[_suite] self-test", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    print("usage: python3 schema/_suite.py --self-test  (the hardening arms' self-check)")
    sys.exit(2)
