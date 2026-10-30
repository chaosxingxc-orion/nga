#!/usr/bin/env python3
"""Deterministic, read-only export of the accepted 2026-10-31 baseline snapshot.

This validates report/audit bindings and metric agreement, not model inference anew.
Pending cells are deliberately frozen and require a later reviewed snapshot to update.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

BASE = Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
KEV = Path('/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev')
OMNI = Path('/mnt/cephfs/xingchao/omni/repos/jev')
PREFIX = 'experiments/REFERENCE-BASELINE-MATRIX-2026-10-31'
MODELS = {'kev08': 'Kev-0.8B', 'kev4': 'Kev-4B', 'kev9': 'Kev-9B',
          'nimble': 'Nimble-9B', 'openjev2': 'Open-Jev-2B', 'openjev9': 'Open-Jev-9B'}
FORMULAS = {
    'kev': 'Question-weighted hard accuracy; summed one-hot multiclass Brier; 10 equal-width bins of top confidence against hard correctness; NLL from recorded logits where available, otherwise probability floor 1e-9. Only n/accuracy/Brier/ECE/NLL independently accepted here.',
    'nimble': 'Hard-reference argmax accuracy; one-hot summed multiclass Brier; Noul binary Brier=(p_true-y)^2 separately; top-confidence hard ECE10; NLL on reference class; score MAE=abs(probability-expected level-reference level), in original level units. Civil distribution JSD uses base 2; TV=0.5*sum(abs(p-q)).',
    'typed': 'Each question has equal weight. Accuracy compares first argmax(p) with first argmax(q). Original rounded gold masses are not renormalized; prediction probabilities are normalized. KL(q||p) uses floor 1e-9; Brier=sum((p-q)^2); ECE10 uses hard argmax correctness/top probability. Strict and original arithmetic both retained; these are probability arithmetic results, not full native wire/HTTP reproduction.',
    'openjev': 'Hard accuracy only on 10046 one-hot rows; all-row expected accuracy=mean(q[argmax(p)]), NLL=-mean(sum(q*log(p))), Brier=mean(sum((p-q)^2)), expected Brier=Brier+mean(1-sum(q^2)); all-row denominator 10532. ECE15 uses expected correctness q[argmax(p)] and top confidence.'}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source(path, pointer=None):
    out = {'path': str(path), 'sha256': sha(path)}
    if pointer:
        out['json_pointer'] = pointer
    return out


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hash_matches(path, expected):
    require(sha(path) == expected, f'Hash mismatch: {path}')


def same(actual, expected, label='metrics'):
    """Audit floating arithmetic tolerates only negligible reduction differences."""
    if isinstance(expected, dict):
        for key, value in expected.items():
            require(key in actual, f'{label}: missing {key}')
            same(actual[key], value, f'{label}/{key}')
    elif isinstance(expected, list):
        require(len(actual) == len(expected), f'{label}: list length')
        for i, (a, e) in enumerate(zip(actual, expected)):
            same(a, e, f'{label}/{i}')
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=1e-12, rel_tol=1e-12), f'{label}: metric mismatch')
    else:
        require(actual == expected, f'{label}: value mismatch')


def finish_bound(root, ap, audit):
    """Bind this audit to the successful finisher that produced its exact bytes."""
    tp = ap.parent / 'FINISH_COMPLETE.json'
    terminal = load(tp)
    require(terminal['rc'] == 0 and terminal['status'] == 'COMPLETED_SCOPED',
            f'Finisher not successfully completed: {tp}')
    require(terminal['inference_run'] == str(root), f'Finisher run mismatch: {tp}')
    hash_matches(root / 'config.json', terminal['config_sha256'])
    require(ap.name in terminal['outputs'], f'Finisher missing audit binding: {tp}')
    for name, digest in terminal['outputs'].items():
        hash_matches(ap.parent / name, digest)
    if 'review_flag_count' in terminal:
        require(terminal['review_flag_count'] == len(audit['review_flags']),
                f'Finisher review flag count mismatch: {tp}')
    return tp


def audit_bound(root):
    ap = root.parent / (root.name + '_finish') / 'INDEPENDENT_AUDIT.json'
    a = load(ap)
    require(a['status'] == 'VERIFIED_SCOPED', f'Not verified: {ap}')
    tp = finish_bound(root, ap, a)
    hash_matches(root / 'report.json', a['report_sha256'])
    hash_matches(root / 'config.json', a['config_sha256'])
    return ap, a, tp


def base_row(group, model, dataset, protocol, temperature, metrics, sources):
    return {'group': group, 'model': MODELS[model], 'dataset': dataset,
            'protocol': protocol, 'temperature': temperature, 'formula_id': group,
            'metrics': metrics, 'sources': sources, 'upstream': None,
            'upstream_absence_reason': 'No matching upstream panel available.'}


def kev_rows():
    rows = []
    spec = [('test', 'decision-v7', 'clean', 1200, 'locked_decision'),
            ('test', 'transfer-v4', 'clean', 656, 'locked_transfer'),
            ('extended', 'hard-v1', 'clean', 1088, 'hard_test'),
            ('extended', 'documents-v1', 'clean', 936, 'docs1_test'),
            ('devtools', 'devtools-v1', 'full', 1073, None),
            ('devtools', 'devtools-v1', 'release', 1071, 'devtools_test')]
    for code, release in [('kev08', 'kev-08b-r15'), ('kev4', 'kev-4b-r10'), ('kev9', 'kev-9b-r27')]:
        upath = KEV / f'runs/release/{release}.json'
        upstream = load(upath)['candidate']
        for kind, suite, population, n, upkey in spec:
            root = BASE / f'{code}_{kind}_20261030'
            rp = root / suite / 'report.json'
            report, config = load(rp), load(root / 'config.json')
            ap = root / ('INDEPENDENT_AUDIT_V2.json' if code == 'kev08' and kind == 'test' else 'INDEPENDENT_AUDIT.json')
            if not ap.exists():
                ap = root.parent / (root.name + '_finish') / 'INDEPENDENT_AUDIT.json'
            audit, terminal = load(ap), load(root / 'REFERENCE_COMPLETE.json')
            require(terminal['rc'] == 0 and audit['status'] == 'VERIFIED_SCOPED', f'Incomplete {root}')
            # Legacy inline audits have no audit-SHA terminal. Their inference
            # terminal still binds reports, but must not be called audit-bound.
            tp = finish_bound(root, ap, audit) if ap.parent != root else None
            require(audit['stamp'] == report['stamp'] == terminal['stamp'], f'Stamp mismatch {root}')
            hash_matches(rp, terminal['suites'][suite]['report_sha256'])
            hash_matches(rp, load(root / 'report.json')['suite_reports'][suite]['report_sha256'])
            data = next(x for x in config['suites'] if x['name'] == suite)
            audited = audit['suites'][suite]
            if kind == 'devtools':
                audited = audited[population]
            for variant in ('native', 'raw_temperature_one'):
                original = report[variant][population]
                m = {k: original[k] for k in ('n', 'acc', 'brier', 'ece', 'nll')}
                same(m, audited[variant], f'{code}/{suite}/{population}/{variant}')
                require(m['n'] == n, f'Denominator mismatch {code}/{suite}/{population}')
                row = base_row('kev', code, suite + '/' + population, variant,
                    report['native_serving_temperature'] if variant == 'native' else 1.0, m,
                    [source(rp, f'/{variant}/{population}'), source(ap), source(root / 'config.json'), source(root / 'REFERENCE_COMPLETE.json')]
                    + ([source(tp)] if tp else []))
                row.update(audit_status=audit['status'], audit_scope=audit['scope'], review_flags=audit.get('review_flags'),
                    audit_terminal_binding='successful_finisher_sha256' if tp else 'absent_legacy_inline_audit',
                    dataset_identity=data, denominators={'records_in_run': report['records'], 'questions_in_run': report['questions'], 'scored_questions': n}, limitations=report.get('limitations'))
                if variant == 'native' and upkey and upstream.get(upkey):
                    u = upstream[upkey]
                    require(u['n'] == n, 'Upstream denominator mismatch')
                    row['upstream'] = {'source': source(upath, '/candidate/' + upkey), 'temperature': upstream['temperature'],
                        'metrics': {k: u.get(k) for k in m}, 'comparison_scope': 'Aggregate metrics only; individual outputs may differ.'}
                elif variant == 'native' and suite == 'documents-v1' and code == 'kev4':
                    p = KEV / 'runs/fam-4b-docs1test/report.json'
                    u = load(p)['clean']
                    require(u['n'] == n, '4B documents denominator mismatch')
                    row['upstream'] = {'source': source(p, '/clean'), 'temperature': None,
                        'metrics': {'n': n, 'acc': u['acc'], 'brier': None, 'ece': None, 'nll': None},
                        'comparison_scope': 'Accuracy only; serving-temperature calibration comparability not established.'}
                if row['upstream'] is not None:
                    row['upstream_absence_reason'] = None
                rows.append(row)
    return rows


def nimble_upstream(path):
    """Parse Nimble's own columns from the two published tables."""
    result = {}
    for line in path.read_text().splitlines():
        if not line.startswith('| '):
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) == 8 and c[1] in ('choice', 'noul', 'score'):
            result.setdefault(c[0], {}).update(n=int(c[2]), accuracy=float(c[4].split('%')[0]) / 100)
        if len(c) == 11 and c[0] in result and '/' in c[1]:
            result[c[0]].update(ece10=float(c[3]), brier=float(c[5]),
                expected_score_mae=None if c[7] == '—' else float(c[7]), nll=None)
            if c[9] != '—':
                jsd, tv = map(float, c[9].split('/'))
                result[c[0]]['human_distribution'] = {'mean_jensen_shannon_bits': jsd, 'mean_total_variation': tv, 'mean_human_entropy_bits': None}
    return result


def nimble_rows():
    root = BASE / 'nimble_public_test_20261030_v2'
    d, config = load(root / 'report.json'), load(root / 'config.json')
    ap, audit, tp = audit_bound(root)
    same(d['suites'], audit['metrics'], 'Nimble suites')
    upath = OMNI / 'bespokelabsai__nimble/docs/PUBLIC_BENCHMARKS.md'
    values = nimble_upstream(upath)
    rows = []
    for suite, panel in d['suites'].items():
        x = panel['summary']['all']
        m = {'n': x['count'], 'correct': x['correct'], 'accuracy': x['accuracy'],
             'nll': x['mean_negative_log_likelihood'], 'brier': x['mean_multiclass_brier'], 'ece10': panel['calibration']['ece10'],
             'binary_brier': x.get('mean_binary_brier'), 'expected_score_mae': x.get('mean_absolute_score_error')}
        data = next(x for x in config['suites'] if x['name'] == suite)
        require(m['n'] == data['count'] == panel['count'], f'Nimble denominator {suite}')
        require(panel['dataset_sha256'] == data['dataset_sha256'], f'Nimble dataset identity {suite}')
        u = values[suite]
        require(u['n'] == m['n'], f'Nimble upstream denominator {suite}')
        row = base_row('nimble', 'nimble', suite, 'native_T1', 1.0, m,
            [source(root / 'report.json', '/suites/' + suite), source(ap), source(root / 'config.json'), source(tp)])
        row.update(audit_status=audit['status'], audit_scope=audit['scope'], review_flags=audit['review_flags'],
                   audit_terminal_binding='successful_finisher_sha256',
                   dataset_identity=data, human_distribution=panel.get('distribution_agreement'))
        row['upstream'] = {'source': source(upath), 'metrics': {k: v for k, v in u.items() if k != 'human_distribution'},
                           'comparison_scope': 'Published rounded table only; upstream item predictions unavailable.'}
        if 'human_distribution' in u:
            row['upstream']['human_distribution'] = u['human_distribution']
        row['upstream_absence_reason'] = None
        rows.append(row)
    require(sum(r['metrics']['n'] for r in rows) == 1884, 'Nimble reported denominator total')
    return rows


def typed_rows():
    rows = []
    for code in MODELS:
        root = BASE / f'typed_{code}_inference_20261030'
        d, config = load(root / 'report.json'), load(root / 'config.json')
        ap, audit, tp = audit_bound(root)
        require(d['rows'] == 400 and d['questions'] == 2000, f'Typed denominator {code}')
        for variant in ('serving', 'raw_T1'):
            if variant not in d:
                require(code == 'nimble' and variant == 'raw_T1', f'Missing Typed panel {code}/{variant}')
                continue
            panel = d[variant]
            expected_panel = audit['panels'] if code == 'nimble' else audit['panels'][variant]
            same(panel, expected_panel, f'Typed {code}/{variant}')
            require(panel['strict']['expected'] == panel['strict']['valid'] == 2000, 'Typed strict coverage')
            require(sum(x['n'] for x in panel['by_type'].values()) == 2000, 'Typed type coverage')
            m = dict(panel['original_arithmetic_raw_readout'], expected_score_mae=None)
            row = base_row('typed', code, 'Typed Decisions test', variant, config.get('temperature', 1.0) if variant == 'serving' else 1.0,
                           m, [source(root / 'report.json', '/' + variant), source(ap), source(root / 'config.json'), source(tp)])
            row.update(audit_status=audit['status'], audit_scope=audit['scope'], review_flags=audit['review_flags'],
                       audit_terminal_binding='successful_finisher_sha256',
                       strict=panel['strict'], by_type=panel['by_type'], by_workflow=panel['by_workflow'],
                       dataset_identity={'path': config['data'], 'sha256': config['files'][config['data']]},
                       denominators={'records': 400, 'questions': 2000}, limitations=[d.get('wire_scope', d.get('scope')), 'Expected-score MAE not yet accepted; null is not zero.'])
            rows.append(row)
    return rows


def open_rows():
    rows = []
    for code in ('openjev2', 'openjev9'):
        root = BASE / f'{code}_original_test_join_20261030'
        d, plan, terminal = load(root / 'report.json'), load(root / 'plan.json'), load(root / 'JOIN_COMPLETE.json')
        require(terminal['rc'] == 0, 'Open-Jev join incomplete')
        hash_matches(root / 'plan.json', terminal['plan_sha256'])
        for name, digest in terminal['outputs'].items():
            hash_matches(root / name, digest)
        require(d['rows'] == 10532 and d['hard_count'] == 10046 and d['soft_count'] == 486, 'Open-Jev denominator mismatch')
        upath = OMNI / f'Zefan-Cai__Open-Jev/reports/full-data-eval-n1-v1/{code[-1]}b-audit.json'
        upstream = load(upath)
        require(d['original_data_sha256'] == upstream['data_identity']['split_sha256']['test'], 'Open-Jev upstream dataset mismatch')
        u = upstream['metrics']['test']['probability_metrics_all_rows']
        for variant in ('serving', 'raw_T1'):
            m = d['metrics'][variant]
            require(m['count'] == 10532 and m['hard_count'] == 10046, 'Open-Jev panel denominator')
            row = base_row('openjev', code, 'Original release-v2 test', variant,
                           d['temperature'] if variant == 'serving' else 1.0, m,
                           [source(root / 'report.json', '/metrics/' + variant), source(root / 'plan.json'), source(root / 'JOIN_COMPLETE.json')])
            row.update(audit_status=d['status'], audit_scope=d['scope'], review_flags=d['review_flags'],
                       components=d['components'], dataset_identity={'path': plan['original_data'], 'sha256': d['original_data_sha256']},
                       denominators={'all_rows': 10532, 'hard_accuracy_rows': 10046, 'soft_rows': 486})
            if variant == 'serving':
                row['upstream'] = {'source': source(upath, '/metrics/test/probability_metrics_all_rows'), 'temperature': upstream['checkpoint']['temperature'],
                                   'metrics': u, 'comparison_scope': 'Aggregate comparison on restored identical original test. Net correct-count difference is not an exact number of prediction flips; no hardware-cause attribution.'}
                row['upstream_absence_reason'] = None
            rows.append(row)
    return rows


def build():
    rows = kev_rows() + nimble_rows() + typed_rows() + open_rows()
    require(Counter(r['group'] for r in rows) == {'kev': 36, 'nimble': 7, 'typed': 11, 'openjev': 4}, 'Matrix coverage mismatch')
    require(len({(r['model'], r['dataset'], r['protocol']) for r in rows}) == 58, 'Duplicate matrix cells')
    pending = [{'model': MODELS[c], 'dataset': 'JEVal', 'status': 'pending_acceptance', 'metrics': None,
                'reason': 'Inference in progress at this snapshot; no completed accepted test metrics.'} for c in ('kev08', 'kev4', 'kev9', 'nimble')]
    pending += [{'model': MODELS[c], 'dataset': 'Open-Jev original OOD', 'status': 'pending_acceptance', 'metrics': None,
                 'reason': 'Inference in progress at this snapshot; no completed accepted test metrics.'} for c in ('openjev2', 'openjev9')]
    pending += [{'model': MODELS[c], 'dataset': 'JEVal', 'status': 'blocked_numerical_admission', 'metrics': None,
                 'reason': 'E36 candidate batching equivalence=false; an exit-zero probe is not numerical admission.'} for c in ('openjev2', 'openjev9')]
    return {'schema_version': 1, 'snapshot_date': '2026-10-31', 'row_counts': dict(Counter(r['group'] for r in rows)),
            'completed_panels': 58, 'formulas': FORMULAS, 'rows': rows, 'pending_cells': pending,
            'scope': 'Read-only consolidation of existing inference experiments, before training-plan discussion. No new model training or production integration.',
            'validation': 'Available report/terminal/audit hash bindings, primary metric agreement, matrix cell coverage and reported denominators checked by exporter; no rerun of inference or independent re-audit of raw predictions. Legacy Kev inline audits lack a successful terminal binding their audit SHA; each affected panel explicitly records this limitation.',
            'limitations': ['No cross-dataset averages.', 'Missing metrics are null, never zero.', 'No new training-benefit claim.', 'Original flags and audit scope retained; no adversarial review approval inferred.', 'Legacy Kev-0.8B native test and all Kev extended/devtools inline audits have report-hash inference terminals and stamp/metric agreement, but no audit-SHA finisher terminal; exporter hashes their current audit files without establishing historical terminal binding.', 'Snapshot excludes later completed runs until their accepted reports are explicitly integrated.']}


def fmt(x, percent=False):
    return '—' if x is None else f'{x * 100:.6f}' if percent else f'{x:.9f}' if isinstance(x, float) else str(x)


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows]


def render(doc):
    rows = doc['rows']
    out = ['# 参考模型测试集指标矩阵（2026-10-31）', '',
           '先汇报参考推理实验，再讨论 Jev 训练方案。本快照汇总 **58 个已完成计分面板**：Kev 36、Nimble 7、Typed Decisions 11、Open-Jev 原 test 4。面板数量包含同一预测的不同温度计分，并不代表 58 次独立推理。', '',
           'JSON 保留完整精度、公式、分母、文件路径及 SHA256、指标 JSON pointer、审计范围和原始 review flags。表中 `—` 对应 JSON 的 `null`，不是零分。当前尚未完成参考指标汇报，因此不能从这些结果直接宣称新训练的收益。', '',
           '## 1. Kev 原生五套 test', '',
           '原生温度：0.8B = 2.3510958125672174；4B = 2.406050072164233；9B = 2.193649959389252。下表 Brier 为 one-hot multiclass 求和，ECE 为 10 bins。clean 分母：decision 1200、transfer 656、hard 1088、documents 936；devtools full 1073 与 release 1071 单列。accuracy 单位为 %。', '']
    out += table(['模型', 'test/子集', '计分', 'n', 'accuracy %', 'Brier', 'ECE10', 'NLL'],
        [[r['model'], r['dataset'], 'native' if r['protocol'] == 'native' else 'T=1', r['metrics']['n'], fmt(r['metrics']['acc'], True), fmt(r['metrics']['brier']), fmt(r['metrics']['ece']), fmt(r['metrics']['nll'])] for r in rows if r['group'] == 'kev'])
    out += ['', '上游同口径的 native 汇总如下。full devtools 与 T=1 无匹配上游列。4B documents 仅验证准确率可比，概率指标留空；上游 NLL 未提供。汇总一致不能证明逐题输出一致。', '']
    out += table(['模型', 'test/子集', '上游 accuracy %', '本地−上游 pp', '上游 Brier', '上游 ECE10'],
        [[r['model'], r['dataset'], fmt(r['upstream']['metrics']['acc'], True), fmt((r['metrics']['acc']-r['upstream']['metrics']['acc'])*100), fmt(r['upstream']['metrics']['brier']), fmt(r['upstream']['metrics']['ece'])] for r in rows if r['group'] == 'kev' and r['upstream']])
    out += ['', '## 2. Nimble 七套原生 test', '', 'T=1，七套是各自上游 test 的冻结子集；不与包含 train/dev/validation 的 3,880 行混合集汇总比较。', '']
    nr = [r for r in rows if r['group'] == 'nimble']
    out += table(['子集', 'n', '本地 accuracy %', '上游 accuracy %', '本地 Brier', '上游 Brier', '本地 ECE10', '上游 ECE10', '本地 NLL'],
        [[r['dataset'], r['metrics']['n'], fmt(r['metrics']['accuracy'], True), fmt(r['upstream']['metrics']['accuracy'], True), fmt(r['metrics']['brier']), fmt(r['upstream']['metrics']['brier']), fmt(r['metrics']['ece10']), fmt(r['upstream']['metrics']['ece10']), fmt(r['metrics']['nll'])] for r in nr])
    out += ['', 'Noul 的 binary Brier 仅取 true 类平方误差，与上表两类求和的 Brier 不同。score MAE 采用期望等级，不采用 argmax 等级或四舍五入。', '']
    out += table(['子集', 'binary Brier', '本地 expected-score MAE', '上游 expected-score MAE'],
        [[r['dataset'], fmt(r['metrics']['binary_brier']), fmt(r['metrics']['expected_score_mae']), fmt(r['upstream']['metrics']['expected_score_mae'])] for r in nr if r['metrics']['binary_brier'] is not None or r['metrics']['expected_score_mae'] is not None])
    civil = next(r for r in nr if r['dataset'] == 'civil_comments')['human_distribution']
    out += ['', f"Civil Comments（300 条）：JSD(base 2)={fmt(civil['mean_jensen_shannon_bits'])}，TV={fmt(civil['mean_total_variation'])}，human entropy={fmt(civil['mean_human_entropy_bits'])} bits。上游 JSD/TV 为 0.176/0.292；不混入 one-hot Brier。", '',
            '## 3. Typed Decisions 六模型共同 test', '',
            '400 records / 2,000 questions；choice 600、Noul 600、score 800。每个问题等权，accuracy 比较预测与 gold 的 first argmax。gold 的原始舍入概率不重新归一化；Brier 为 soft-gold 求和，KL 使用 1e-9 floor；ECE10 仍使用 hard argmax correctness。原计分 arithmetic 与 strict 面板均保留在 JSON；本次各模型 strict 均 2,000 valid。此处是概率读出计分，不等于原生 wire/HTTP 完整复现。', '']
    out += table(['模型', '计分', 'accuracy %', 'KL(gold||p)', 'soft-gold Brier', 'ECE10'],
        [[r['model'], r['protocol'], fmt(r['metrics']['accuracy'], True), fmt(r['metrics']['kl_from_gold']), fmt(r['metrics']['brier']), fmt(r['metrics']['ece10'])] for r in rows if r['group'] == 'typed'])
    out += ['', '每个 type/workflow 的完整分数见 JSON。Nimble 原生已是 T=1，不重复一个 raw 面板；expected-score MAE 尚未验收，保留 null。当前没有可直接配对的上游同检查点分数。', '',
            '## 4. Open-Jev 原始完整 test', '',
            '原始 release-v2 test 共 10,532 行（已恢复公共部分 10,356 + 缺失补集 176）；其中 hard 10,046、soft 486。hard accuracy 仅用 hard 行；expected accuracy、NLL、Brier、expected Brier、ECE15 用全体行。原生温度 2B=1.518796342858676，9B=1.8969118766347646。', '']
    out += table(['模型', '计分', 'hard accuracy %', 'expected accuracy %', 'NLL', 'Brier', 'expected Brier', 'ECE15'],
        [[r['model'], r['protocol'], fmt(r['metrics']['accuracy'], True), fmt(r['metrics']['expected_accuracy'], True), fmt(r['metrics']['nll']), fmt(r['metrics']['brier']), fmt(r['metrics']['expected_brier']), fmt(r['metrics']['multiclass_ece'])] for r in rows if r['group'] == 'openjev'])
    out += ['', '同一原始 test 的上游 serving 汇总：', '']
    out += table(['模型', '上游 hard accuracy %', '上游 expected accuracy %', 'NLL', 'Brier', 'expected Brier', 'ECE15'],
        [[r['model'], fmt(r['upstream']['metrics']['accuracy'], True), fmt(r['upstream']['metrics']['expected_accuracy'], True), fmt(r['upstream']['metrics']['nll']), fmt(r['upstream']['metrics']['brier']), fmt(r['upstream']['metrics']['expected_brier']), fmt(r['upstream']['metrics']['multiclass_ece'])] for r in rows if r['group'] == 'openjev' and r['upstream']])
    out += ['', '本地 hard 正确数 2B=9,507、9B=9,796；上游分别 9,515、9,799。净少 8/3 个正确不代表恰好 8/3 道题发生翻转，也不足以归因于硬件。原报告中的 perfect-source、小样本等 review flags 原样保留；通过结构化验收不抹去这些限制。', '',
            '## 5. 尚未形成验收分数的单元', '']
    out += table(['模型', '数据集', '状态', '指标'], [[r['model'], r['dataset'], r['status'], 'null'] for r in doc['pending_cells']])
    out += ['', 'JEVal 四模型与原 OOD 两模型在快照时继续执行。Open-Jev JEVal 的候选批处理数值准入失败；即使探针退出码为零，也不能作为准入通过。后续需按预注册完成诊断、通过准入、执行、独立验收后再补指标。', '',
            '## 6. 指令顺序与验收边界', '',
            '参考推理实验是当前第一阶段实验的一部分；其自动启动、断点续跑、终态验收和结果汇总必须完成。先补齐上述矩阵及各文献计算口径，再据此讨论 Jev 训练方案及符合目标的可检验收益。取消算力预算不取消数值准入、预注册或正确性验收；真实业务接入仍不在本阶段范围。', '',
            '导出器只读取结构化报告：核对已有的终态/报告/审计哈希绑定、报告与独立审计的主要指标、报告中的分母及 58 个矩阵面板覆盖。Typed、Nimble 与 Kev-4B/9B 原生 test 的审计 SHA 必须绑定成功 finisher 终态；缺失终态、非零退出或哈希变更均拒绝导出。Kev-0.8B 原生 test 及全部 Kev extended/devtools 属于旧版 inline audit：核对推理终态中的报告 SHA、stamp 与指标一致性，但没有绑定审计 SHA 的 finisher 终态，JSON 逐面板标为 absent_legacy_inline_audit；本次计算当前审计文件 SHA 不会补造历史绑定。', '',
            '上述检查不重新运行模型，不重新检查原始逐题回执，也不替代既有逐题审计或构成额外的对抗审查批准。不同数据集不做平均分；不从参考模型得分直接推断新训练增益。', '',
            '复现命令：`python3 -P tools/export_reference_baseline_matrix.py`。运行须可读取快照引用的 CephFS 文件；输出为同名 JSON 与 Markdown。相同输入生成逐字节相同输出。']
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, default=Path(PREFIX + '.json'))
    parser.add_argument('--md', type=Path, default=Path(PREFIX + '.md'))
    args = parser.parse_args()
    doc = build()
    args.json.write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    args.md.write_text(render(doc))
    print(json.dumps({'completed_panels': doc['completed_panels'], 'row_counts': doc['row_counts'], 'pending_cells': len(doc['pending_cells'])}))


if __name__ == '__main__':
    main()
