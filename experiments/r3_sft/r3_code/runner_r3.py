"""Minimal test runner (no pytest on the hosts): `python3 -P test_x_r3.py` runs every top-level test_* function of the module,
prints PASS / FAIL per test and exits non-zero on any failure. Each test names the prereg clause it asserts in its name and
docstring (R3-SFT-PREREG sec 10.5: a clause is in force only when a test naming it asserts it)."""
import sys
import time
import traceback


def run(namespace, only=None):
    tests = [(n, f) for n, f in namespace.items() if n.startswith("test_") and callable(f)]
    failed = 0
    tests = [(n, f) for n, f in tests if not only or only in n]
    for name, fn in tests:
        t0 = time.time()
        try:
            fn()
            print(f"PASS {name} ({time.time() - t0:.1f}s)", flush=True)
        except Exception:    # noqa: BLE001
            failed += 1
            print(f"FAIL {name}\n{traceback.format_exc()}", flush=True)
    print(f"{len(tests) - failed} passed, {failed} failed", flush=True)
    return 1 if failed else 0


def main(namespace):
    sys.exit(run(namespace, sys.argv[1] if len(sys.argv) > 1 else None))
