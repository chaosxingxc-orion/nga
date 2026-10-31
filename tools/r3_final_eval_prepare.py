"""Build a separate deferred-publication evaluator from the pinned producer.

This is a source preparation tool, not a final launcher or approval mechanism.
The guarded entry requires live reservations supplied by the transaction owner.
Existing frozen jobs are never modified. Ordinary test execution is disabled in
the generated module. Final admission and recovery verification remain external.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = '16e8401a2b90dbafbdbe6f82f0bbfa25aab48e51fb4ed1b4ce842e25d88d0b8c'

AUTH = '''    tickets = {}
    if "test" in a.partitions:
        if a.limit or a.limit_groups:
            raise C.TestLockRefusal("sec 8.4: a limited read of a test partition still counts as the one read; --limit is refused with test")
        for suite in C.SUITES:
            tickets[(suite, "test")] = TL.authorize_test_read(identity, suite, "test", a.round_dir)
        log("test partitions authorized: " + ", ".join(f"{s}/{p}" for s, p in tickets))
'''
COMMIT = '''    for ticket, n, acc in reads:        # sec 8.4 step 3, after every number is computed and before any report is written
        line = TL.record_test_read(ticket, n, acc, a.round_dir, run_dir=out)
        log("TEST-READS.log: " + line)
        report.setdefault("test_reads", []).append(line)
'''

BRIDGE = '''
def run_full(a, score_fn):
    partitions = a.partitions.split(",") if isinstance(a.partitions, str) else a.partitions
    if "test" in partitions:
        raise C.TestLockRefusal("test requires the guarded transaction entry")
    return _run_full_deferred(a, score_fn)


def _check_test_leases(a, leases, owner):
    # This capability prevents accidental entry outside the owning transaction;
    # it is not an authorization boundary against arbitrary Python execution.
    import json as _json
    import r3_test_transaction as _TX
    _G = _TX.G
    expected_suites = {"decision-v7", "transfer-v4"}
    if set(leases) != expected_suites:
        raise C.TestLockRefusal("both live test reservations required")
    expected_owner = {k: owner[k] for k in ("run_dir", "execution_sha256", "final_sha256")}
    if expected_owner["run_dir"] != str(_G.safe_path(a.out)):
        raise C.TestLockRefusal("output differs from reservation")
    round_root = _G.safe_path(a.round_dir)
    final = round_root / "FINAL.json"
    _G.safe_path(final)
    if C.sha256_file(str(final)) != owner["final_sha256"]:
        raise C.TestLockRefusal("FINAL changed")
    for suite in sorted(expected_suites):
        lease = leases[suite]
        key = {"model_sha256": owner["model_sha256"], "suite": suite, "partition": "test"}
        expected_path = round_root / "test-execution-reservations" / (_G.digest(key) + ".json")
        _G.safe_path(expected_path)
        if (not isinstance(lease, _G.Reservation) or not lease.active
                or lease.path != expected_path or lease.value.get("key") != key
                or lease.value.get("owner") != expected_owner or lease.value.get("state") != "reserved"
                or _json.loads(expected_path.read_text()) != lease.value):
            raise C.TestLockRefusal("live reserved execution identity differs")


def run_guarded_test(a, score_fn, *, leases, owner):
    partitions = a.partitions.split(",") if isinstance(a.partitions, str) else a.partitions
    if (sorted(partitions) != ["calibration", "test"] or a.stages != "k"
            or a.limit or a.limit_groups or a.shard != 0 or a.num_shards != 1
            or a.k_only or a.b4_base or a.unit_tag
            or a.dtype != "float32" or not a.no_hf32 or not a.require_record_grade
            or a.device != "npu" or a.model_path.startswith("mock")):
        raise C.TestLockRefusal("final scoring requires full calibration/test Track K of record")
    _check_test_leases(a, leases, owner)
    identity = TL.model_identity(a.model_path, a.adapter, a.round_dir)
    if identity["sha256"] != owner["model_sha256"]:
        raise C.TestLockRefusal("model differs from reservation")
    tickets = {(suite, "test"): TL.authorize_test_read(identity, suite, "test", a.round_dir)
               for suite in ("decision-v7", "transfer-v4")}
    report = _run_full_deferred(a, score_fn, _test_tickets=tickets)
    _check_test_leases(a, leases, owner)
    return report, tickets
'''


def transform(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('source differs from frozen evaluator')
    text = source.decode('utf-8')
    signature = 'def run_full(a, score_fn):'
    for block in (signature, AUTH, COMMIT):
        if text.count(block) != 1:
            raise ValueError('source transformation anchor differs')
    text = text.replace(signature, 'def _run_full_deferred(a, score_fn, *, _test_tickets=None):', 1)
    text = text.replace(AUTH, '''    tickets = {}
    if "test" in a.partitions:
        if _test_tickets is None or set(_test_tickets) != {(s, "test") for s in C.SUITES}:
            raise C.TestLockRefusal("guarded test tickets required")
        tickets = _test_tickets
        if any(t.identity != identity or t.suite != s or t.split != p
               for (s, p), t in tickets.items()):
            raise C.TestLockRefusal("test ticket model or partition differs")
''', 1)
    text = text.replace(COMMIT, '''    if reads:
        report["test_publication"] = {"state": "unpublished", "scientific_acceptance": False}
''', 1)
    text += '\n' + BRIDGE
    ast.parse(text)
    # The numerical Track K implementation must remain structurally identical.
    def track(tree):
        return ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_track_k'))
    if track(ast.parse(source)) != track(ast.parse(text)):
        raise ValueError('Track K metric implementation changed')
    return text


def prepare(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('output must be a new preparation directory')
    generated = transform(source.read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'full_eval_r3.py'
    target.write_text(generated)
    manifest = {'schema': 'r3-final-evaluator-preparation-v1', 'source': str(source),
                'source_sha256': SOURCE_SHA256,
                'generated_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'scientific_acceptance': False, 'deployable': False,
                'remaining': ['pinned full code closure and exact-plan final launcher',
                              'transaction lease integration and recovery-only evidence verification',
                              'real producer integration validation and independent review']}
    (output / 'PREPARATION.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))
