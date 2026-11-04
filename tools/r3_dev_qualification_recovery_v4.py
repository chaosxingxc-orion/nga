"""Restore first-K1 selection semantics; retain void Track T diagnostics.

Dated implementation correction: 2026-11-04. SFT §§8.2,9.2,14.10 and
wave §4 do not make first-K1 adoption conditional on a nonvoid repeat flip
floor. Both full repeat experiments and accuracy floors remain mandatory.
Replacement behavior and every frozen scientific threshold are unchanged.
"""
import hashlib
import math
import types
from pathlib import Path

_p = Path(__file__).with_name('r3_dev_qualification_recovery_v3.py')
_raw = _p.read_bytes()
if hashlib.sha256(_raw).hexdigest() != '7cac0a52442804e7ae55e43d88e3fc725191e28d4f9d409a6b7d15434c161050':
    raise ValueError('v3 composition source changed')
V = types.ModuleType('recovered_qualification_v3'); V.__file__ = str(_p)
exec(compile(_raw, str(_p), 'exec'), V.__dict__)
Q = V.Q
_original_numerical = Q.numerical


def typed_diagnostics(primary, repeats, active):
    """Validate complete raw evidence without conferring consistency validity."""
    Q.require(set(repeats) == {'samechip', 'diffchip'}, 'both named auxiliary roles required')
    Q.require(len(primary) == 2 and active, 'primary/R0 population missing')
    reports = {'primary_s2': primary[0], 'primary_s3': primary[1], **repeats}
    cells = {}
    for kind in active:
        by_role = {}
        for role, report in reports.items():
            c = report['track_t']['selection']['typed-decisions'][kind]
            Q.require(type(c['n_units']) is int and c['n_units'] > 0
                      and type(c['n_pairs_used']) is int and c['n_pairs_used'] > 0
                      and type(c['n_pairs_dropped_tie']) is int and c['n_pairs_dropped_tie'] >= 0,
                      'empty/invalid floor population')
            Q.require(c['b2_status'] in ('pass', 'fail', 'void'), 'invalid B2 diagnostic state')
            for key in ('flip_T1_argmax', 'b2_gap'):
                value = c[key]
                Q.require(type(value) in (int, float) and math.isfinite(value), 'nonfinite typed diagnostic')
            Q.require(0 <= c['flip_T1_argmax'] <= 1 and -1 <= c['b2_gap'] <= 1,
                      'typed diagnostic out of range')
            by_role[role] = {key: c[key] for key in ('b2_status', 'b2_gap', 'n_units',
                                                   'n_pairs_used', 'n_pairs_dropped_tie', 'flip_T1_argmax')}
        original = by_role['primary_s2']
        comparisons = {}
        for role in repeats:
            other = by_role[role]
            Q.require(original['n_units'] == other['n_units'], 'floor structural unit population differs')
            void = any(c['b2_status'] == 'void' for c in (original, other))
            comparisons[role] = {
                'difference': None if void else abs(original['flip_T1_argmax'] - other['flip_T1_argmax']),
                'status': 'VOID_OPERAND' if void else 'DESCRIPTIVE_ONLY',
                'reason': 'A void operand cannot support a scientific flip floor.' if void else 'First-K1 has no replacement flip-margin gate.',
                'gating': False,
                'denominators': [original['n_pairs_used'], other['n_pairs_used']],
                'dropped_ties': [original['n_pairs_dropped_tie'], other['n_pairs_dropped_tie']],
            }
        cells[kind] = {'observations': by_role, 'comparisons': comparisons, 'gating': False}
    return {'scope': 'First-K1 non-gating typed diagnostics; raw void values are not valid consistency claims.',
            'cells': cells, 'changes_adoption_gate': False}


def numerical(reports, gate, api, branch='firstK1'):
    if branch != 'firstK1':
        # Includes the original unknown-branch refusal and all replacement logic.
        return _original_numerical(reports, gate, api, branch)
    q = api.Q
    primary = [reports[r] for r in ('primary_s2', 'primary_s3')]
    repeats = {k: reports[k+'_s2'] for k in ('samechip', 'diffchip')}
    result = q.numeric(branch, primary, reports['k0_base'], [], repeats, gate, api)
    active = [k for k, v in gate['statuses'].items() if v in ('pass', 'fail')]
    Q.require(active, 'empty R0 gating population')
    # q.numeric firstK1 already checks both full repeats, their recipe, identities
    # and all common protocol fields, and computes both accuracy noise floors.
    # Do not overwrite that result with replacement-only eligibility diagnostics.
    result['firstk1_typed_floor_diagnostics'] = typed_diagnostics(primary, repeats, active)
    result['floor_policy'] = 'Full samechip and diffchip evidence mandatory; no new threshold for first-K1. Only diffchip gates later registered replacement margins.'
    result.pop('broad_floor_applicability', None)
    qo = api.S._dev_acc(reports['qo_s2'], 'transfer-v4')
    result['semantic_transfer_seal'] = {'reference': 'SFT5.5', 'qo_accuracy': qo,
        'per_seed': {str(r['selection_evidence']['seed']): {
            'accuracy': api.S._dev_acc(r, 'transfer-v4'),
            'gap': api.S._dev_acc(r, 'transfer-v4') - qo,
            'semantic_transfer_claim': api.S._dev_acc(r, 'transfer-v4') - qo >= .05-api.S.EPS} for r in primary},
        'changes_adoption_gate': False}
    result['control_metrics'] = {name: {s: api.S._dev_acc(reports[name], s) for s in q.SUITES} for name in Q.CONTROLS}
    result['numeric_predicates_scope'] = 'Registered K-floor, current-wave absolute lines, K0 guard and admitted R0 dependency; replacement additionally uses registered 8.2(a,b,c). Controls and both full floors validated separately.'
    result['floor_indeterminate'] = False
    result['floor_qualification_indeterminate'] = False
    return result


Q.numerical = numerical
for name in ('source_api', 'protocol', 'read_boundary', 'evaluate', 'main', 'entries',
             'chronology', 'member', 'verify_prelaunch', 'training_runtime', 'evaluation_runtime'):
    globals()[name] = getattr(Q, name)
if __name__ == '__main__':
    raise SystemExit(main())
