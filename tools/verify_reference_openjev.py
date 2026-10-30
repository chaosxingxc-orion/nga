#!/usr/bin/env python3
"""Independent stdlib verification of frozen Open-Jev public-test artifacts.

Does not import the inference driver or native metrics. Verifies artifact identity,
complete coverage and every reported probability metric; it does not establish
unseen generalization, upstream training provenance or cross-device equivalence.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, 0o644); os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def distribution(values):
    require(isinstance(values, list) and len(values) >= 2, 'Invalid distribution shape')
    require(all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values), 'Invalid distribution value')
    total = sum(values)
    require(math.isclose(total, 1, rel_tol=1e-6, abs_tol=1e-6), 'Distribution mass differs')
    return [x / total for x in values]


def probabilities(logits, temperature):
    require(type(temperature) in (int, float) and math.isfinite(temperature) and temperature > 0, 'Invalid temperature')
    require(isinstance(logits, list) and len(logits) >= 2 and
            all(type(x) in (int, float) and math.isfinite(x) for x in logits), 'Invalid logits')
    weights = [math.exp((x - max(logits)) / temperature) for x in logits]
    return [x / sum(weights) for x in weights]


def metrics(targets, predictions):
    require(len(targets) == len(predictions) > 0, 'Metric denominator mismatch')
    observed = []
    errors = [0.0] * 15
    nll = brier = expected_brier = 0.0
    for target, prediction in zip(targets, predictions):
        q, p = distribution(target), distribution(prediction)
        require(len(q) == len(p), 'Target size differs')
        k = p.index(max(p)); confidence, correct = p[k], q[k]
        observed.append((confidence, correct, max(q) == 1.0))
        errors[min(int(confidence * 15), 14)] += confidence - correct
        nll -= sum(y * math.log(max(x, 1e-15)) for x, y in zip(p, q))
        distance = sum((x - y) ** 2 for x, y in zip(p, q))
        brier += distance
        expected_brier += distance + 1 - sum(y * y for y in q)
    def subset(rows):
        hard = [correct for _, correct, is_hard in rows if is_hard]
        accuracy = sum(hard) / len(hard) if hard else None
        expected = sum(v[1] for v in rows) / len(rows) if rows else None
        return {'selected': len(rows), 'coverage': len(rows)/len(observed), 'accuracy': accuracy,
                'expected_accuracy': expected, 'expected_risk': 1-expected if expected is not None else None}
    all_rows = subset(observed); n = len(observed)
    return {'count': n, 'hard_count': sum(v[2] for v in observed), 'accuracy': all_rows['accuracy'],
            'expected_accuracy': all_rows['expected_accuracy'], 'nll': nll/n, 'brier': brier/n,
            'expected_brier': expected_brier/n, 'multiclass_ece': sum(abs(x) for x in errors)/n,
            'ece_bins': 15, 'coverage': [{'threshold': t, **subset([v for v in observed if v[0] >= t])}
                                     for t in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)]}


def same(actual, expected, path='report'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), path + ': keys differ')
        for k in expected: same(actual[k], expected[k], path + '/' + k)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), path + ': list differs')
        for i, (a,b) in enumerate(zip(actual, expected)): same(a,b,path+'/'+str(i))
    elif type(expected) is float:
        require(type(actual) in (float, int) and math.isfinite(actual) and
                math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12), path + ': metric differs')
    else:
        require(type(actual) is type(expected) and actual == expected, path + ': value differs')


def terminal(run, mode, identity, config_sha, output, stage):
    path = run / (mode + '-COMPLETE.json'); t = load(path)
    require(type(t.get('rc')) is int and t['rc'] == 0 and t.get('error') is None, mode + ': failed terminal')
    require(t.get('identity') == identity and t.get('config_sha256') == config_sha and t.get('stage') == stage,
            mode + ': terminal identity/stage differs')
    require(t.get('outputs', {}).get(output) == sha(run/output), mode + ': output hash differs')
    wrapper = run / (mode + '-EXIT')
    require(re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?', wrapper.read_text()) is not None,
            mode + ': failed wrapper')
    require(wrapper.stat().st_mtime_ns >= path.stat().st_mtime_ns >= (run/output).stat().st_mtime_ns,
            mode + ': stale terminal/wrapper')
    return t


def required_files(c):
    run = Path(c['out'])
    paths = {str(Path(c[k]).resolve()) for k in ('data', 'export_manifest', 'preregistration')}
    # Derive executable dependencies independently, not from execution_files alone.
    paths.update(str((run/n).resolve()) for n in ('openjev_reference_eval.py','launch.sh','preflight.sh',
                 'evaluate.sh','PREFLIGHT_EXACT.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'))
    for key in ('code', 'base', 'checkpoint'):
        root = Path(c[key]); require(root.is_dir(), 'Missing dependency root: ' + key)
        paths.update(str(p.resolve()) for p in root.rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return paths


def verify(config_path, dataset_validator=None):
    config_path=Path(config_path); c=load(config_path); run=Path(c['out'])
    identity=object_sha(c); config_hash=sha(config_path)
    needed=required_files(c)
    require(needed <= set(c['files']), 'Required frozen dependency omitted')
    for path, expected in c['files'].items(): require(sha(path)==expected, 'Frozen file changed: '+path)
    require(not any((run/n).exists() for n in ('ERROR.json','FAILED','evaluate-FAILED','preflight-FAILED')), 'Recorded failure conflicts with completion')
    launch=load(run/'LAUNCH_RECEIPT.json')
    require(launch['config_sha256']==config_hash and launch['wrapper_sha256']==sha(run/'evaluate.sh')
            and launch['image']==c['image'] and launch['command']==['bash', str(run/'evaluate.sh')], 'Launch binding differs')
    preterm=terminal(run,'preflight',identity,config_hash,'PREFLIGHT.json','ready')
    end=terminal(run,'evaluate',identity,config_hash,'report.json','complete')
    rows=[json.loads(line) for line in Path(c['data']).read_text().splitlines()]
    manifest=(dataset_validator(c, rows) if dataset_validator else
              load(c['export_manifest'])['configs']['release-v2-redistributable']['splits']['test'])
    require(sha(c['data'])==manifest['raw_uncompressed_sha256'], 'Data manifest hash differs')
    require(len(rows)==c['expected_rows']==manifest['count'], 'Input count differs')
    require(len({r['id'] for r in rows})==len(rows), 'Duplicate input IDs')
    require(c.get('expected_split','test') in ('test','ood') and
            all(r['split']==c.get('expected_split','test') for r in rows), 'Wrong evaluation split')
    require(dict(Counter(r['source'] for r in rows))==manifest['sources'] and
            dict(Counter(r['kind'] for r in rows))==manifest['kinds'], 'Source/kind counts differ')
    model=load(Path(c['checkpoint'])/'model.json')
    require((model['model_id'],model['revision'],model['max_length'])==
            (c['base_id'],c['base_revision'],c['max_length']), 'Checkpoint protocol differs')
    require(Path(c['base'],'.complete').read_text().splitlines()[0]==c['base_revision'], 'Base revision differs')
    require(load(Path(c['checkpoint'])/'temperature.json')['temperature']==c['temperature'], 'Temperature differs')
    names=[f'record-{i:06d}.json' for i in range(len(rows))]
    require(sorted(p.name for p in run.glob('record-*.json'))==names, 'Inference coverage differs')
    require(sorted(p.name for p in (run/'lengths').glob('record-*.json'))==names, 'Length coverage differs')
    values=[]; maximum=prompt_count=0
    for i,(name,row) in enumerate(zip(names,rows)):
        require(row['kind'] in ('choice','noul','score') and len(row['target'])==len(row['options']), 'Input shape differs')
        distribution(row['target'])
        if row['kind']=='noul': require(row['options']==['no','yes'], 'Noul candidate order differs')
        envelope=load(run/name); value=envelope['payload']
        require(object_sha(value)==envelope['sha256'], 'Receipt hash differs: '+name)
        expected={'index':i,'id':row['id'],'input_sha256':object_sha(row),'identity':identity,
                  **{k:row[k] for k in ('options','target','source','kind','group_id')}}
        for k,v in expected.items(): require(value.get(k)==v,'Receipt identity/order differs: '+name+'/'+k)
        require(len(value['logits'])==len(row['options']), 'Logit count differs')
        same(value['probabilities'],probabilities(value['logits'],c['temperature']),name+'/probabilities')
        length=load(run/'lengths'/name); payload=length['payload']
        require(object_sha(payload)==length['sha256'], 'Length receipt hash differs')
        for k in ('index','id','input_sha256','identity'): require(payload.get(k)==expected[k], 'Length identity differs')
        lens=payload['lengths']
        require(len(lens)==(1 if row['kind']=='noul' else len(row['options'])) and
                all(type(n) is int and 0<n<=c['max_length'] for n in lens), 'Length bound differs')
        require(type(value['input_tokens']) is int and value['input_tokens']==sum(lens), 'Model token count differs')
        maximum=max(maximum,max(lens)); prompt_count+=len(lens); values.append(value)
    hard=sum(max(r['target'])==1 for r in rows)
    require(hard==c['hard_count'], 'Hard denominator differs')
    pre=load(run/'PREFLIGHT.json')
    for k,v in {'identity':identity,'rows':len(rows),'max_length':c['max_length'],'maximum_candidate_tokens':maximum,
                'candidate_prompts':prompt_count,'overlength_rows':0,'overlength_candidates':0,'overlength':[],
                'ordered_ids_sha256':object_sha([r['id'] for r in rows]),'status':'ready','test_inference_performed':False}.items():
        same(pre[k],v,'preflight/'+k)
    for t in (preterm,end):require(t['progress']==t['total']==len(rows),'Terminal coverage differs')
    report=load(run/'report.json')
    for k,v in {'identity':identity,'total_count':len(rows),'hard_count':hard,'soft_count':len(rows)-hard,
                'failed_count':0,'serving_temperature':c['temperature'],
                'ordered_ids_sha256':object_sha([r['id'] for r in rows]),
                'tie_count':sum(v['logits'].count(max(v['logits']))>1 for v in values)}.items():same(report[k],v,k)
    result={}
    def compute(indices,temp): return metrics([rows[i]['target'] for i in indices],
                                              [probabilities(values[i]['logits'],temp) for i in indices])
    for key,temp in [('serving',c['temperature']),('raw_T1',1.0)]:
        result[key]=compute(range(len(rows)),temp);same(report[key],result[key],key)
    for field,key in [('source','by_source_serving'),('kind','by_kind_serving')]:
        groups=defaultdict(list)
        for i,r in enumerate(rows):groups[r[field]].append(i)
        result[key]={k:compute(v,c['temperature']) for k,v in sorted(groups.items())}
        same(report[key],result[key],key)
    flags=[]
    cells={'serving':result['serving'],'raw_T1':result['raw_T1'],
           **{f'by_source_serving/{k}':v for k,v in result['by_source_serving'].items()},
           **{f'by_kind_serving/{k}':v for k,v in result['by_kind_serving'].items()}}
    for key,v in cells.items():
        pointer=str(run/'report.json')+'#/'+key
        if v['count']<30:flags.append({'reason':'sample_count_below_30','count':v['count'],'pointer':pointer})
        for metric in ('accuracy','expected_accuracy','nll','brier','expected_brier','multiclass_ece'):
            if v[metric] in (0.0,1.0):flags.append({'reason':'exact_zero_or_one','metric':metric,'pointer':pointer+'/'+metric})
    sources=result['by_source_serving']
    for key in ('accuracy','expected_accuracy','nll','brier','expected_brier','multiclass_ece'):
        if len(sources)>1 and len({v[key] for v in sources.values()})==1:
            flags.append({'reason':'identical_across_sources','metric':key,'pointer':str(run/'report.json')+'#/by_source_serving'})
    require(sha(config_path)==config_hash, 'Config changed during audit')
    for path, expected in c['files'].items(): require(sha(path)==expected, 'Frozen file changed during audit: '+path)
    terminal(run,'evaluate',identity,config_hash,'report.json','complete')
    return {'status':'VERIFIED_SCOPED_REVIEW_REQUIRED' if flags else 'VERIFIED_SCOPED',
            'identity':identity,'records_verified':len(rows),'hard_count':hard,'soft_count':len(rows)-hard,
            'frozen_files_verified':len(c['files']),'required_files_verified':len(needed),
            'config_sha256':config_hash,'report_sha256':sha(run/'report.json'),
            'metrics':result,'review_flags':flags,
            'scope':'Complete artifact coverage and native/raw probability metrics; not Astra approval, upstream provenance, or generalization.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=verify(a.config);atomic(a.out,result)
    print(json.dumps({'status':result['status'],'records_verified':result['records_verified'],'review_flags':len(result['review_flags'])}))


if __name__=='__main__':main()
