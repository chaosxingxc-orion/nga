#!/usr/bin/env python3
"""Freeze a control DEV package using unchanged scoring and core lifecycle.

Preparation performs no resource observation/claim, service launch or activation.
The physical predecessor may still be training; its immutable launch generation
is pinned now and its terminal/release evidence is required dynamically later.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import types

BASE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
SOURCES={'relocation','launcher','resource_core','guard_core','control_guard',
         'control_resource','cpu_controller','cpu_report'}
def require(ok,why):
    if not ok:raise RuntimeError(why)
def safe(p):
    p=Path(p);require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p
def sha(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def pin(p):return {'path':str(p),'sha256':sha(p)}
def pinned(ref):
    require(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'input pin differs');return safe(ref['path'])
def module(ref):
    p=pinned(ref);m=types.ModuleType(p.stem);m.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec',dont_inherit=True),m.__dict__);return m
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write(chr(10))

def inspect(path,config_pin):
    require(sha(path)==config_pin,'config changed');c=read(path)
    require(set(c)=={'schema','prepared','spec','closure','cpu_template','sources','root','container',
                    'control_config','control_controller','previous_generation','wiki_preregistration_required'},'config fields differ')
    require(c['schema']=='r3-control-dev-prepare-v1' and c['wiki_preregistration_required']is True,'prepare scope differs')
    require(set(c['sources'])==SOURCES,'source interfaces differ')
    for ref in c['sources'].values():pinned(ref)
    for key in ['prepared','spec','closure','cpu_template','control_config','control_controller']:pinned(c[key])
    spec=read(c['spec']['path']);receipt=read(c['prepared']['path']);manifest=read(c['closure']['path'])
    require(receipt['status']=='prepared' and receipt['role']=='qo_s2' and receipt['plan']==c['spec']['path']
            and receipt['sha256']==c['spec']['sha256'] and receipt['evaluation_authorized']is False
            and receipt['test_read']is False and receipt['scientific_acceptance']is False,'exact QO handoff differs')
    require(spec['training_variant']['arm']=='k1-qo' and spec['training_variant']['seed']==2
            and spec['execution_review']==spec['chip_assignment']=='PENDING','QO identity differs')
    module(c['sources']['launcher']).verify_spec(spec,Path(c['spec']['path']).parent)
    require(spec['code_mounts']==manifest['mounts'],'original closure mount differs')
    closure=Path(c['closure']['path']).parent
    for entry in manifest['code'].values():
        source=pinned({'path':entry['snapshot'],'sha256':entry['sha256']})
        require(source.is_relative_to(closure) and spec['files'].get(str(source))==entry['sha256'],'closure source differs')
    root=safe(c['root']);require(root.is_relative_to(BASE) and root!=BASE and not root.exists(),'fresh run root required')
    require(c['container'].startswith('nga-r3-eng-eval-') and all(x.isalnum() or x in '-_' for x in c['container']),'container differs')
    return c,spec,manifest

def prepare(path,config_pin):
    c,spec,manifest=inspect(path,config_pin);root=Path(c['root']);root.mkdir();out=root/'evaluation'
    for p in [out,root/'cpu',root/'tools',root/'source-closure']:p.mkdir()
    clean=root/'source-closure';closure=Path(c['closure']['path']).parent;mapping={}
    for e in manifest['code'].values():
        source=Path(e['snapshot']);target=clean/source.relative_to(closure);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target);require(sha(target)==e['sha256'],'source copy differs');mapping[str(source)]=str(target);e['snapshot']=str(target)
    for m in manifest['mounts']:m['source']=str(clean/Path(m['source']).relative_to(closure))
    write(clean/'manifest.json',manifest)
    relocation=module(c['sources']['relocation'])
    derived=relocation.relocate_spec(spec,Path(c['spec']['path']).parent,out,closure,clean,mapping)
    write(out/'plan.json',derived)
    names={'launcher':'r3_posttrain_eval_launcher.py','resource_core':'r3_resource_adapter.py',
           'cpu_controller':'r3_cpu_report_queue.py','cpu_report':'r3_selection_report.py'}
    for key,name in names.items():
        shutil.copyfile(c['sources'][key]['path'],root/'tools'/name);require(sha(root/'tools'/name)==c['sources'][key]['sha256'],'tool copy differs')
    launcher=module(pin(root/'tools/r3_posttrain_eval_launcher.py'));execution,unused=launcher.bind(out/'plan.json',3,c['container'])
    p=read(execution);td=out/'execution-tools'
    added={'guard_core':'core_formal_dev_successor.py','resource_core':'core_resource_adapter.py',
           'control_guard':'r3_control_dev_successor_v1.py','control_resource':'r3_control_dev_resource_v1.py'}
    for key,name in added.items():shutil.copyfile(c['sources'][key]['path'],td/name);require(sha(td/name)==c['sources'][key]['sha256'],'guard source copy differs')
    p['resource_adapter']=str(td/'r3_control_dev_resource_v1.py');p['tools']={str(f):sha(f) for f in td.iterdir() if f.is_file()}
    p['adapter']=p['resource_adapter'];p['files']=dict(p['tools'])
    p['successor_guard']={'schema':'r3-control-dev-guard-v1','identity_mode':'sha256_raw',
        'controller':str(td/'r3_control_dev_successor_v1.py'),'predecessor_kind':'control_training',
        'training_role':'qo_s2','training_job':'qo_seed2','previous_job':'pt_seed2',
        'original_spec':c['spec'],'prepared':c['prepared'],'control_config':c['control_config'],
        'control_controller':c['control_controller'],'previous_generation':c['previous_generation']}
    # bind created this new, unlaunched file; freeze its final composed content once.
    execution.write_text(json.dumps(p,sort_keys=True,indent=2)+chr(10))
    config={'schema':'r3-formal-dev-successor-v1','execution':pin(execution),'state_root':str(root/'guard-state'),
            'wake_source':pin(root/'tools/r3_cpu_report_queue.py'),'poll_interval_seconds':600,
            'test_read':False,'scientific_acceptance':False,
            'event_wake_paths':[str(Path(c['previous_generation']['plan']['path']).parent/n) for n in
                                ['TRAIN_EXIT.json','attempts/1/RELEASE.json','attempts/1/SUPERVISOR_DONE.json']]}
    config['config_identity']=hashlib.sha256((json.dumps(config,sort_keys=True,indent=2)+chr(10)).encode()).hexdigest()
    write(root/'CONFIG.json',config)
    guard=module(pin(td/'r3_control_dev_successor_v1.py'));guard.verify(root/'CONFIG.json',sha(root/'CONFIG.json'))
    queue=read(c['cpu_template']['path']);queue.update(closure=str(clean),closure_sha256=sha(clean/'manifest.json'),
             producer_closure={'path':str(clean),'manifest_sha256':sha(clean/'manifest.json')})
    for key,name in [('controller','r3_cpu_report_queue.py'),('report_tool','r3_selection_report.py')]:
        queue[key]=str(root/'tools'/name);queue[key+'_sha256']=sha(queue[key])
    queue['jobs']=[{'id':'qo-seed2-formal-dev','kind':'report','eval_out':str(out),'output':str(out/'results/selection_report.json'),
                   'plan':str(out/'plan.json'),'plan_sha256':sha(out/'plan.json'),'execution':str(execution),
                   'execution_sha256':sha(execution),'terminal_gate':'full_posttrain_v1'}]
    queue['event_wake_paths']=[str(out/n) for n in ['ENGINEERING_EVAL_EXIT.json','attempts/1/SUPERVISOR_DONE.json']]
    write(root/'cpu/queue.json',queue);module(pin(Path(queue['controller']))).verify(root/'cpu/queue.json',sha(root/'cpu/queue.json'))
    derivation={'schema':'r3-control-dev-derivation-v1','configuration':{'path':str(path),'sha256':config_pin},
                'original_spec':c['spec'],'new_spec':pin(out/'plan.json'),'source_map':mapping,
                'source_files_copied':len(mapping),'changes_only':['readonly source copy paths','results/identity output paths'],
                'new_interfaces':['control identity/predecessor binding','explicit registered control guard resource entry'],
                'scoring_bytes_unchanged':True,'metrics_thresholds_population_unchanged':True,'launch_authorized':False}
    write(root/'DERIVATION.json',derivation)
    result={'schema':'r3-control-dev-preparation-v1','status':'PREPARED_PENDING_INDEPENDENT_REVIEW_AND_PT_RELEASE',
            'role':'qo_s2','chip':3,'config':pin(root/'CONFIG.json'),'config_identity':config['config_identity'],
            'execution':pin(execution),'spec':pin(out/'plan.json'),'cpu_queue':pin(root/'cpu/queue.json'),
            'derivation':pin(root/'DERIVATION.json'),'guard':pin(td/'r3_control_dev_successor_v1.py'),
            'missing':['independent exact implementation/configuration review','prelaunch wiki publication',
                       'root authenticated activation','PT seed2 actual terminal/release and matching live free generation'],
            'launch_authorized':False,'npu_started':False,'cpu_started':False,'test_read':False,'scientific_acceptance':False}
    write(root/'PREPARATION.json',result);return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('op',choices=['verify','prepare']);parser.add_argument('--config',required=True);parser.add_argument('--sha256',required=True);a=parser.parse_args()
    if a.op=='verify':inspect(a.config,a.sha256);print('CONTROL_DEV_PREPARE_CONFIG_VERIFIED')
    else:print(json.dumps(prepare(a.config,a.sha256),indent=2))
if __name__=='__main__':main()
