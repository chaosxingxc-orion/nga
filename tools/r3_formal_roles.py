"""Prospective four-run role contract. Validation never grants launch authority."""
import hashlib
import json
from pathlib import Path

ROLES = ('primary_s2', 'primary_s3', 'samechip_s2', 'diffchip_s2')
FIELDS = ('formal_schedule', 'formal_schedule_sha256', 'formal_role')

def require(ok, why):
    if not ok: raise RuntimeError(why)

def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe role path')
    return p

def sha(path): return hashlib.sha256(safe(path).read_bytes()).hexdigest()

def command_recipe(command):
    c=list(command)
    require(c.count('--out')==c.count('--seed')==1,'recipe output/seed ambiguous')
    for key in ('--out','--seed'): c[c.index(key)+1]='<ROLE>'
    return c

def validate_schedule(d):
    require(d.get('schema')=='r3-formal-role-schedule-v1' and d.get('scientific_acceptance') is False
            and d.get('test_read') is False,'role schedule scope differs')
    require(d.get('floor_gating_role')=='diffchip_s2' and d.get('samechip_gates') is False
            and d.get('floor_replicates_excluded_from_all_candidate_estimators') is True,'floor policy differs')
    nodes=d.get('nodes',[]); require(len(nodes)==8 and len({x['id'] for x in nodes})==8,'eight unique schedule nodes required')
    by={n['id']:n for n in nodes};require(set(by)==set(ROLES)|{r+'_dev' for r in ROLES},'role inventory differs')
    require(len({n['out'] for n in nodes})==8 and len({by[r]['container'] for r in ROLES})==4,'duplicate output/container')
    chips=d['physical_chips']; require(len(chips)==2 and len(set(chips))==2 and all(type(x) is int and 0<=x<8 for x in chips),'physical chips differ')
    primary=by['primary_s2']; recipe=command_recipe(primary['command_candidate'])
    for role in ROLES:
        n=by[role];seed=3 if role=='primary_s3' else 2;chip=chips[0] if role in ('primary_s2','samechip_s2') else chips[1]
        require(n.get('kind')=='training' and n.get('role')==role and n.get('seed')==seed and n.get('chip')==chip and n.get('steps')==3116,'training role/chip/seed differs')
        require(n.get('candidate_for_seed_mean') is role.startswith('primary_'),'auxiliary candidate membership differs')
        safe(n['out']);c=n['command_candidate'];require(c[c.index('--out')+1]==n['out'] and c[c.index('--seed')+1]==str(seed) and command_recipe(c)==recipe,'role recipe differs')
        dev=by[role+'_dev'];safe(dev['out'])
        require(dev.get('kind')=='dev_calibration_track_t_readout' and dev.get('training_id')==role and dev.get('chip')==chip and dev.get('test_read') is False and dev.get('same_scorer_and_population_as_primary') is True,'DEV role mapping differs')
    expected={'samechip_s2':['primary_s2_release'],'diffchip_s2':['primary_s3_release'],
              'primary_s2_dev':['samechip_s2_release'],'samechip_s2_dev':['primary_s2_dev_release'],
              'primary_s3_dev':['diffchip_s2_release'],'diffchip_s2_dev':['primary_s3_dev_release']}
    for name,deps in expected.items():require(by[name].get('depends_on')==deps,'role ordering differs')
    require(isinstance(d.get('shared_inputs'),dict) and d['shared_inputs'],'shared input pins required')
    require(set(d.get('code_by_relative_path',{})) >= {'train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py'},'shared training code pins required')
    return by

def validate_plan(p):
    require(all(k in p for k in FIELDS),'partial formal role binding')
    path=safe(p['formal_schedule']);require(sha(path)==p['formal_schedule_sha256'] and p['files'].get(str(path))==p['formal_schedule_sha256'],'schedule pin differs')
    d=json.loads(path.read_text());by=validate_schedule(d);role=p['formal_role'];require(role in ROLES,'unknown formal role');n=by[role]
    require(p.get('control_arm') is None and p.get('formal_chips')==d['physical_chips'],'common wave/control binding differs')
    for k in ('seed','chip','out','container'):require(p[k]==n[k],'plan role '+k+' differs')
    require(p['command']==n['command_candidate'],'plan role recipe differs')
    require(p['evaluation'].get('candidate_for_adoption') is n['candidate_for_seed_mean'],'plan auxiliary candidate membership differs')
    require({k:v for k,v in p['files'].items() if k.startswith(p['model']+'/')} ==
            {k:v for k,v in d['shared_inputs'].items() if k.startswith(p['model']+'/')},'complete model inventory differs')
    for name,h in d['shared_inputs'].items():require(p['files'].get(name)==h and sha(name)==h,'shared model/data input differs')
    for rel,h in d['code_by_relative_path'].items():
        q=safe(str(Path(p['code'])/rel));require(q.is_relative_to(Path(p['code'])) and p['files'].get(str(q))==h and sha(q)==h,'shared training code differs')
    require(p['train_file'] in d['shared_inputs'] and any(x.startswith(p['model']+'/') for x in d['shared_inputs']),'model/train pins missing')
    return {'role':role,'schedule_sha256':p['formal_schedule_sha256'],'candidate_for_adoption':n['candidate_for_seed_mean'],
            'seed':n['seed'],'primary_seed2_chip':d['physical_chips'][0],'chip':n['chip']}
