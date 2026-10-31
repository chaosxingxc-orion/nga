#!/usr/bin/env python3
"""Bounded receipt-metadata progress only: no readout/log reads or completion verdict."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re

MAX_JSON_BYTES = 1 << 20
MAX_OUTPUT_BYTES = 262144


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts, 'absolute non-traversing path required')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path refused')
    return p


def metadata(path):
    p = safe(path)
    require(p.is_file() and p.stat().st_size <= MAX_JSON_BYTES, 'missing/oversize metadata')
    return json.loads(p.read_text())


def population(path, pin):
    p = safe(path)
    require(p.is_file() and p.stat().st_size <= MAX_JSON_BYTES, 'invalid population file')
    raw = p.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == pin, 'population pin differs')
    d = json.loads(raw)
    require(d.get('schema') == 'r3-inference-workload-cpu-audit-v1' and
            all(d.get(k) is False for k in ('test_read','scores_read','scientific_acceptance')), 'population scope differs')
    require(d.get('roles') == {'primary':'full','empty_input':'blank','question_only':'drop'}, 'roles differ')
    expected = {}
    def add(name, count, track):
        require(name not in expected and type(count) is int and count > 0, 'invalid/duplicate population cell')
        expected[name] = (count, track)
    for row in d['track_k']:
        parts = row['cell'].split('/')
        require(len(parts)==3, 'invalid K cell')
        suite, split, kind = parts
        require(suite in ('decision-v7','transfer-v4') and split in ('dev','calibration') and
                kind in ('clean','variants','question_only','empty_input'), 'invalid K cell component')
        add(f'trackk/{suite}__{split}/{kind}.jsonl',row['records'],'track_k')
    for row in d['track_t']:
        task, source = row['task'], row['source']
        require(task in ('T1','T2','T3') and source in ('typed-decisions','openjev-synth','akhilaaa3'), 'invalid T cell')
        for role in d['roles']:
            add(f'trackt/readouts/{role}__{task}__{source}__shard0of1.jsonl',row['records_per_role'],'track_t')
    required_k = {f'trackk/{suite}__{split}/{kind}.jsonl'
                  for suite,split in [('decision-v7','dev'),('decision-v7','calibration'),('transfer-v4','dev')]
                  for kind in (('clean','question_only','empty_input') if split=='calibration' else
                               ('clean','variants','question_only','empty_input'))}
    required_t = {f'trackt/readouts/{role}__{task}__{source}__shard0of1.jsonl'
                  for role in d['roles'] for task in ('T1','T2','T3')
                  for source in (('typed-decisions',) if task=='T3' else ('typed-decisions','openjev-synth','akhilaaa3'))}
    require(set(expected)==required_k|required_t, 'population inventory differs')
    k = sum(n for n,t in expected.values() if t=='track_k')
    t = sum(n for n,tr in expected.values() if tr=='track_t')
    require(k==d['track_k_records']==9516 and t==d['track_t_records_all_roles']==139026 and
            t//3==d['records_per_role']==46342 and k+t==d['total_records']==148542, 'population totals differ')
    return expected


def summarize(run, expected):
    root = safe(run)
    flags = Counter(); details=[]; valid=[]; missing=0
    def flag(kind, rel):
        flags[kind]+=1
        if len(details)<32: details.append({'kind':kind,'path':str(rel)[:240]})
    for rel,(count,track) in expected.items():
        data=root/rel; receipt=Path(str(data)+'.receipt.json')
        try:
            safe(receipt);safe(data)
            if not receipt.exists(): missing+=1;continue
            d=metadata(receipt)
            require(d.get('path')==str(data), 'receipt path mismatch')
            n=d.get('rows'); size=d.get('committed_bytes')
            require(type(n) is int and 0<=n<=count, 'receipt row count invalid')
            require(type(size) is int and size>=0 and (n==0 or size>0), 'receipt byte count invalid')
            require(data.is_file() and size<=data.stat().st_size, 'committed data missing or truncated')
            require(isinstance(d.get('model_sha256'),str) and re.fullmatch('[0-9a-f]{64}',d['model_sha256']), 'model metadata invalid')
            require(isinstance(d.get('scorer'),dict) and d['scorer'], 'scorer metadata invalid')
            require(isinstance(d.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',d['sha256']), 'digest metadata invalid')
            identity=(d['model_sha256'],json.dumps(d['scorer'],sort_keys=True))
            valid.append((rel,n,track,identity))
            if n<count:flag('incomplete_receipt',rel)
        except (ValueError, OSError, TypeError, KeyError) as e:
            flag('invalid_receipt',rel+': '+str(e))
    # Enumerate filenames only; never open unexpected receipt or score content.
    if root.exists():
        require(root.is_dir(), 'run must be a directory')
        for directory,dirs,files in os.walk(root,followlinks=False):
            for name in list(dirs):
                if (Path(directory)/name).is_symlink():
                    flag('symlink_directory',str((Path(directory)/name).relative_to(root)));dirs.remove(name)
            for name in files:
                if not name.endswith('.receipt.json'):continue
                p=Path(directory)/name;rel=str(p.relative_to(root))
                if rel[:-len('.receipt.json')] not in expected:flag('unexpected_receipt',rel)
    else:flag('missing_root','.')
    if len({x[3] for x in valid})>1:
        flag('inconsistent_model_or_scorer','all otherwise valid receipts excluded')
        valid=[]
    totals={track:{'receipt_reported_rows':sum(n for _,n,t,_ in valid if t==track),
                   'expected_rows':sum(n for n,t in expected.values() if t==track)} for track in ('track_k','track_t')}
    done=sum(x['receipt_reported_rows'] for x in totals.values());total=sum(x['expected_rows'] for x in totals.values())
    return {'run':str(root),'receipt_reported_rows':done,'expected_rows':total,
            'record_fraction':done/total,'record_percent':100*done/total,
            'tracks':totals,'valid_receipts':len(valid),'expected_receipts':len(expected),
            'missing_receipts':missing,'flags':dict(flags),'flag_details':details,'flag_details_capped_at':32,
            'completion':'not_assessed','scientific_acceptance':False,'scores_read':False,
            'scope':'receipt metadata and data stat only; no byte/provenance/quality verification; record fraction is not time fraction'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--population',required=True);p.add_argument('--population-sha256',required=True)
    p.add_argument('--run',action='append',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();require(len(a.run)<=16 and len(set(a.run))==len(a.run), 'at most sixteen unique runs')
    expected=population(a.population,a.population_sha256)
    result={'schema':'r3-inference-progress-metadata-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'population_sha256':a.population_sha256,'runs':[summarize(r,expected) for r in a.run]}
    raw=json.dumps(result,indent=2,allow_nan=False)+'\n';require(len(raw.encode())<=MAX_OUTPUT_BYTES,'digest size cap exceeded')
    output=safe(a.output)
    with output.open('x') as f:f.write(raw)
    for r in result['runs']:
        print(json.dumps({k:r[k] for k in ('run','receipt_reported_rows','expected_rows','record_percent','flags','completion')}))


if __name__=='__main__':main()
