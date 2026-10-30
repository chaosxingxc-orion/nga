#!/usr/bin/env python3
"""Verify both completed components and recompute exact original-test metrics."""
import argparse
import fcntl
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import time


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v = sibling('verify_reference_openjev')
p = sibling('openjev_original_protocol')


def join_records(full, components, positions):
    """Join untouched component envelopes, retaining provenance for every original row."""
    public, supplement = components
    p.validate_partition(full, public['rows'], supplement['rows'], positions)
    v.require(p.model_signature(public['config']) == p.model_signature(supplement['config']),
              'Component model protocol differs')
    lookup = {}
    for component in components:
        config = component['config']; identity = v.object_sha(config)
        rows = component['rows']; receipts = component['receipts']
        v.require(len(rows) == len(receipts), 'Component receipt denominator differs')
        for i, (row, envelope) in enumerate(zip(rows, receipts)):
            value = envelope['payload']
            v.require(v.object_sha(value) == envelope['sha256'], 'Changed receipt payload')
            expected = {'index': i, 'id': row['id'], 'input_sha256': v.object_sha(row), 'identity': identity,
                        **{k: row[k] for k in ('options', 'target', 'source', 'kind', 'group_id')}}
            v.require(all(value.get(k) == value2 for k,value2 in expected.items()), 'Receipt row/config binding differs')
            v.require(row['id'] not in lookup, 'Duplicate joined ID')
            v.same(value['probabilities'], v.probabilities(value['logits'], config['temperature']))
            v.require(len(value['logits']) == len(row['target']), 'Candidate count differs')
            lookup[row['id']] = {'component': component['name'], 'component_index': i,
                                'config_identity': identity, 'receipt_sha256': envelope['sha256'],
                                'input_sha256': v.object_sha(row), 'logits': value['logits']}
    v.require(set(lookup) == {row['id'] for row in full}, 'Joined coverage differs')
    result = [{'original_index': i, 'id': row['id'], **lookup[row['id']]} for i,row in enumerate(full)]
    for row, value in zip(full,result):
        v.require(value['input_sha256'] == v.object_sha(row), 'Original row payload differs')
    return result


def summarize(full, joined, temperature):
    v.require(len(full) == len(joined) > 0, 'Joined denominator differs')
    def metric(indices, temp):
        return v.metrics([full[i]['target'] for i in indices],
                         [v.probabilities(joined[i]['logits'],temp) for i in indices])
    result = {'serving': metric(range(len(full)),temperature), 'raw_T1': metric(range(len(full)),1.0)}
    for field,key in [('source','by_source_serving'),('kind','by_kind_serving')]:
        groups = defaultdict(list)
        for i,row in enumerate(full): groups[row[field]].append(i)
        result[key] = {name: metric(indices,temperature) for name,indices in sorted(groups.items())}
    return result


def verify_container(config):
    f = sibling('openjev_reference_finish')
    run = Path(config['out']); receipt = v.load(run/'LAUNCH_RECEIPT.json')
    v.require(f.inspect_state(f.container_info(config['container']),receipt,config) == 'exited',
              'Component container has not exited successfully')


def _execute(plan_path):
    plan = v.load(plan_path); out = Path(plan['out'])
    v.require(not (out/'JOIN_COMPLETE.json').exists() and not (out/'report.json').exists(),
              'Prior join requires reviewed fresh output')
    plan_hash = v.sha(plan_path)
    required = {str(Path(__file__).resolve()), str(Path(__file__).with_name('verify_reference_openjev.py').resolve()),
                str(Path(__file__).with_name('verify_openjev_supplement.py').resolve()),
                str(Path(__file__).with_name('openjev_original_protocol.py').resolve()),
                str(Path(__file__).with_name('openjev_reference_finish.py').resolve()),
                str(Path(plan['preregistration']).resolve()), str(Path(plan['public_config']).resolve()),
                str(Path(plan['supplement_config']).resolve()), str(Path(plan['original_data']).resolve()),
                str(Path(plan['restoration_report']).resolve())}
    v.require(required <= set(plan['files']), 'Join dependencies omitted')
    for path, expected in plan['files'].items(): v.require(v.sha(path) == expected, 'Join input changed: '+path)
    public = v.load(plan['public_config']); supplement = v.load(plan['supplement_config'])
    v.require(Path(supplement['parent_config']).resolve() == Path(plan['public_config']).resolve(), 'Wrong public parent')
    v.require(v.sha(plan['original_data']) == p.FULL_SHA, 'Original full-test hash mismatch')
    audits = [v.verify(plan['public_config']), sibling('verify_openjev_supplement').verify(plan['supplement_config'])]
    for c in (public,supplement): verify_container(c)
    components = []
    for name,config in [('public',public),('supplement',supplement)]:
        rows = [json.loads(line) for line in Path(config['data']).read_text().splitlines()]
        receipts = [v.load(Path(config['out'])/f'record-{i:06d}.json') for i in range(len(rows))]
        components.append({'name':name,'config':config,'rows':rows,'receipts':receipts})
    full = [json.loads(line) for line in Path(plan['original_data']).read_text().splitlines()]
    positions = v.load(plan['restoration_report'])['missing_public_rows']['test']['original_line_numbers']
    joined = join_records(full,components,positions)
    metrics = summarize(full,joined,public['temperature'])
    flags = [{'reason':'component_review_required','component':component['name'],
              'audit_identity':audit['identity'],'report_sha256':audit['report_sha256'],
              'flag':flag}
             for component,audit in zip(components,audits) for flag in audit['review_flags']]
    for panel in ['serving','raw_T1']:
        for key,value in metrics[panel].items():
            if type(value) is float and value in (0.0,1.0): flags.append({'panel':panel,'metric':key,'reason':'exact_zero_or_one'})
    for panel in ['by_source_serving','by_kind_serving']:
        for name,cell in metrics[panel].items():
            if cell['count'] < 30: flags.append({'panel':panel,'cell':name,'reason':'sample_count_below_30'})
            for key in ('accuracy','expected_accuracy','nll','brier','expected_brier','multiclass_ece'):
                if cell[key] in (0.0,1.0): flags.append({'panel':panel,'cell':name,'metric':key,'reason':'exact_zero_or_one'})
        if len(metrics[panel]) > 1:
            for key in ('accuracy','expected_accuracy','nll','brier','expected_brier','multiclass_ece'):
                if len({cell[key] for cell in metrics[panel].values()}) == 1:
                    flags.append({'panel':panel,'metric':key,'reason':'identical_across_cells'})
    for path,expected in plan['files'].items(): v.require(v.sha(path) == expected,'Join input changed during audit')
    v.require(v.sha(plan_path) == plan_hash, 'Join plan changed')
    for c,audit in zip((public,supplement),audits):
        verify_container(c)
        run=Path(c['out'])
        v.terminal(run,'evaluate',v.object_sha(c),audit['config_sha256'],'report.json','complete')
        v.require(v.sha(run/'report.json')==audit['report_sha256'],'Component report changed during join')
    v.atomic(out/'joined-records.json',joined)
    report = {'status':'VERIFIED_ORIGINAL_TEST_REVIEW_REQUIRED' if flags else 'VERIFIED_ORIGINAL_TEST',
              'population':'original release-v2 test', 'rows':len(full),'hard_count':metrics['serving']['hard_count'],
              'soft_count':len(full)-metrics['serving']['hard_count'], 'temperature':public['temperature'],
              'original_data_sha256':p.FULL_SHA, 'joined_records_sha256':v.sha(out/'joined-records.json'),
              'components':[{'name':component['name'],'config_sha256':v.sha(plan[key]),
                             'report_sha256':audit['report_sha256'],'audit_identity':audit['identity'],
                             'audit_status':audit['status'],'review_flags':audit['review_flags']}
                            for component,key,audit in zip(components,['public_config','supplement_config'],audits)],
              'metrics':metrics,'review_flags':flags,'scope':'Exact original-test reference inference; no Astra approval or new training benefit.'}
    v.atomic(out/'report.json',report)
    v.atomic(out/'JOIN_COMPLETE.json',{'rc':0,'plan_sha256':plan_hash,'outputs':{
        name:v.sha(out/name) for name in ('joined-records.json','report.json')},
        'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    return report


def execute(plan_path):
    out=Path(v.load(plan_path)['out'])
    with (out/'join.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _execute(plan_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan',required=True)
    args = parser.parse_args()
    out = Path(v.load(args.plan)['out'])
    prior = (out/'JOIN_COMPLETE.json').exists() or (out/'report.json').exists()
    try:
        execute(args.plan)
    except BaseException as exc:
        if not prior:
            v.atomic(out/'JOIN_COMPLETE.json',{'rc':1,'error_type':type(exc).__name__,
                'error':str(exc),'plan_sha256':v.sha(args.plan),
                'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        raise
