#!/usr/bin/env python3
"""Derive reviewable E41 release tools from the accepted E40 release source.

This preparation tool writes a NEW code directory only. It neither approves nor
executes release. Each generated executable pins exactly one caller-pinned plan.
The resulting source and its tests require independent review before use.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
SOURCE_SHA256 = '431bbe0c85c23f001c0705169b37bb4ddcb523216a792ba069336c2f408e6ced'
HELPER_SHA256 = '12a5e895d6fa16df0506418dfbad0affe584cd06e62993a40bee0b4d86ee5b77'
CASES = {
    'openjev9_short': dict(chip=4, model=9, index=4200, shape=[15,186], heads=32, cores=24),
    'openjev2_long': dict(chip=1, model=2, index=8409, shape=[24,3480], heads=16, cores=18),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_replace(source, old, new, count):
    if source.count(old) != count:
        raise ValueError('Frozen release derivation anchor differs: '+old)
    return source.replace(old, new)


def validate_target(case, plan, path, pin):
    if case not in CASES or not re.fullmatch(r'[0-9a-f]{64}', pin):
        raise ValueError('Unknown case or invalid caller plan pin')
    c=CASES[case]
    if (path.name != 'plan.json' or path.parent.parent != ROOT
            or not path.parent.name.startswith('e41_') or plan['out'] != str(path.parent)
            or plan['schema'] != 'e41-full-shape-lifetime-'+case+'-v1'
            or plan['case'] != case or plan['base_id'] != f"Qwen/Qwen3.5-{c['model']}B"
            or plan['physical_chip'] != c['chip'] or plan['candidate_batch_admission'] is not False
            or plan['input']['index'] != c['index'] or plan['input']['shape'] != c['shape']
            or plan['core_shape'] != c['shape']+[c['heads'],128]
            or len(plan['expected_core_names']) != c['cores']):
        raise ValueError('Plan differs from finite E41 release case')


def derive(raw, case, plan, path, pin):
    if sha(raw) != SOURCE_SHA256:
        raise ValueError('E40 release source identity differs')
    validate_target(case,plan,path,pin)
    chip=CASES[case]['chip'];s=raw.decode()
    old="PLAN_HASHES = {'e40_lifetime_npu_openjev2_20261031_v3': '90721d6509df030a71ed012848f7a0b11ce31b7fd11d63c306fbaf90b223c3d9'}"
    s=checked_replace(s,old,'PLAN_HASHES = '+repr({path.parent.name:pin}),1)
    for old,new,count in [
        ('E40 chip-1','E41 '+case+' chip-'+str(chip),1),
        ('e40-resource-release-','e41-resource-release-',4),
        ("'e40_release_'","'e41_release_'",2),
        ("'.e40-'","'.e41-'",1),
        ("p['physical_chip']==1",f"p['physical_chip']=={chip}",1),
        ("intent['chip']==1",f"intent['chip']=={chip}",1),
        ("x['chip']==1",f"x['chip']=={chip}",5),
        ("x['chip']!=1",f"x['chip']!={chip}",2),
        ('dict(chip=1,','dict(chip='+str(chip)+',',1),
        ("-intent-v1',chip=1,","-intent-v1',chip="+str(chip)+',',1),
        ('q.chip_access(d,1)','q.chip_access(d,'+str(chip)+')',1),
        ('prep.free_now(q,1)','prep.free_now(q,'+str(chip)+')',1),
        ('chip 1 historically','chip '+str(chip)+' historically',1),
        ('references chip 1','references chip '+str(chip),1),
        ('exact chip-1 run','exact chip-'+str(chip)+' run',1),
        ('Unreviewed E40 release target','Unreviewed E41 release target',1),
        ('Unknown E40 plan','Unknown E41 plan',1),
        ('Frozen E40 plan changed','Frozen E41 plan changed',1),
    ]:
        s=checked_replace(s,old,new,count)
    # CPU verifier protocol remains E40 v1: its generic authenticated reconstruction
    # loads the E41 plan's frozen protocol. Changing that schema would break binding.
    ast.parse(s)
    return s.encode()


def prepare(case, plan_path, pin, source, helper, out):
    for path in (plan_path,source,helper):
        if any(x.is_symlink() for x in [path,*path.parents]):
            raise ValueError('Symlink source/plan forbidden')
    raw=plan_path.read_bytes()
    if sha(raw)!=pin:
        raise ValueError('Caller-pinned plan differs')
    if sha(helper.read_bytes())!=HELPER_SHA256:
        raise ValueError('Accepted evidence helper differs')
    result=derive(source.read_bytes(),case,json.loads(raw),plan_path,pin)
    out.mkdir(parents=False,exist_ok=False)
    (out/'release_openjev_lifetime.py').write_bytes(result)
    (out/'e38_evidence.py').write_bytes(helper.read_bytes())
    record=dict(schema='e41-release-derivation-v1',case=case,chip=CASES[case]['chip'],
        source=str(source),source_sha256=SOURCE_SHA256,helper_sha256=HELPER_SHA256,
        generator_sha256=sha(Path(__file__).read_bytes()),plan=str(plan_path),plan_sha256=pin,
        output_sha256=sha(result),approved=False,released=False,
        scope='Code derivation only; exact generated code requires review; future live evidence and caller-pinned anchor required')
    (out/'DERIVATION.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES,required=True)
    for name in ('plan','source','helper','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--plan-sha256',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.case,a.plan.absolute(),a.plan_sha256,a.source.absolute(),a.helper.absolute(),a.out.absolute())))
