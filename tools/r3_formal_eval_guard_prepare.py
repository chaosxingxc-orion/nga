#!/usr/bin/env python3
"""Configuration-only packaging for a formal successful DEV-to-DEV guard.

No service starts, resource claims or activation receipts are produced. Existing
packages remain unchanged; a partial destination is retained and never adopted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import types

BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')

def require(ok, why):
    if not ok: raise ValueError(why)

def safe(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p

def sha(p): return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def read(p): return json.loads(safe(p).read_bytes())
def pin(p): return {'path':str(p),'sha256':sha(p)}
def pinned(ref):
    require(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'input pin differs')
    return safe(ref['path'])
def write(p,d):
    with Path(p).open('x') as f: json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def module(p):
    m=types.ModuleType(Path(p).stem);m.__file__=str(p)
    exec(compile(safe(p).read_bytes(),str(p),'exec',dont_inherit=True),m.__dict__);return m

def edge(spec,execution,previous,schedule,previous_ref,schedule_ref):
    role=spec['training_variant']['formal_role_identity'];nodes={n['id']:n for n in schedule['nodes']}
    prior=read(previous['spec'])['training_variant']['formal_role_identity'];name=role['role'];target=name+'_dev';node=nodes[target]
    require(previous['schema']=='r3-engineering-posttrain-execution-v1' and previous['test_read'] is False
            and previous['scientific_acceptance'] is False, 'formal evaluation predecessor required')
    require(node['kind']=='dev_calibration_track_t_readout' and node['training_id']==name
            and node['depends_on']==[prior['role']+'_dev_release'],'registered evaluation edge differs')
    require(type(execution['chip']) is int and execution['chip']==role['chip']==node['chip']==previous['chip']==prior['chip'],'chip differs')
    require(role['schedule_sha256']==schedule_ref['sha256']==prior['schedule_sha256'],'schedule differs')
    require(spec['training']==nodes[name]['out'] and read(previous['spec'])['training']==nodes[prior['role']]['out']
            and str(Path(previous_ref['path']).parent)==previous['out'],'training identity differs')
    return name,target


def relocated(spec,old,new):
    d=json.loads(json.dumps(spec));cmd=d['command']
    for option,leaf in [('--out','results'),('--round-dir','identity')]:
        require(cmd.count(option)==1,'output option differs');i=cmd.index(option)+1
        require(cmd[i]==str(old/leaf),'old output differs');cmd[i]=str(new/leaf)
    return d

def inspect(path,config_pin):
    require(sha(path)==config_pin,'configuration changed');c=read(path)
    require(set(c)=={'schema','prepared','execution','cpu_queue','template_config','previous_execution','previous_original_spec','previous_derivation','guard_controller','schedule','root','container'},'configuration fields differ')
    require(c['schema']=='r3-formal-eval-guard-prepare-v1','configuration schema differs')
    refs={k:pinned(c[k]) for k in ['prepared','execution','cpu_queue','template_config','previous_execution','previous_original_spec','previous_derivation','guard_controller','schedule']}
    receipt=read(refs['prepared']);p=read(refs['execution']);specpath=safe(p['spec']);spec=read(specpath)
    require(receipt['execution_sha256']==c['execution']['sha256'] and receipt['spec_sha256']==sha(specpath)==p['spec_sha256']
            and receipt['cpu_queue_sha256']==c['cpu_queue']['sha256'],'prepared package identity differs')
    require(receipt['launch_authorized'] is False and receipt['npu_started'] is False and receipt['test_read'] is False
            and receipt['scientific_acceptance'] is False and p['test_read'] is False and p['scientific_acceptance'] is False
            and spec['test_read'] is False and spec['scientific_acceptance'] is False,'package authority differs')
    require(Path(p['out'])==refs['execution'].parent and refs['prepared'].parent==Path(p['out']).parent,'package root differs')
    require(p['launcher'] in p['tools'],'launcher not pinned')
    for source,digest in p['tools'].items():
        require(sha(source)==digest,'generic execution tool changed')
    module(p['launcher']).verify(refs['execution'],c['execution']['sha256'])
    q=read(refs['cpu_queue']);require(len(q['jobs'])==1 and q['jobs'][0]['execution']==str(refs['execution'])
        and q['jobs'][0]['execution_sha256']==c['execution']['sha256'] and q['jobs'][0]['terminal_gate']=='full_posttrain_v1','CPU producer differs')
    require(sha(q['controller'])==q['controller_sha256'],'CPU controller differs');module(q['controller']).verify(refs['cpu_queue'],c['cpu_queue']['sha256'])
    template=read(refs['template_config']);tp=read(pinned(template['execution']));g=tp['successor_guard']
    require(sha(g['controller'])==tp['tools'][g['controller']],'template guard changed')
    module(g['controller']).verify(refs['template_config'],c['template_config']['sha256'])
    previous=read(refs['previous_execution']);schedule=read(refs['schedule'])
    role,target=edge(spec,p,previous,schedule,c['previous_execution'],c['schedule'])
    require(receipt['role']==role and receipt['chip']==p['chip'],'prepared role differs')
    root=safe(c['root']);require(root.is_relative_to(BASE) and root!=BASE and not root.exists(),'fresh output required')
    require(isinstance(c['container'],str) and c['container'].startswith('nga-r3-eng-eval-')
            and all(x.isalnum() or x in '-_' for x in c['container']),'container differs')
    return c,refs,p,spec,q,tp,previous,role,target

def prepare(path,config_pin):
    c,refs,p,spec,q,tp,previous,role,target=inspect(path,config_pin)
    root=Path(c['root']);out=root/'evaluation';td=out/'execution-tools';td.mkdir(parents=True)
    (root/'cpu').mkdir();old=Path(p['out']);new_spec=relocated(spec,old,out);write(out/'plan.json',new_spec)
    mapping={}
    for source,h in tp['tools'].items():
        require(sha(source)==h,'template source changed');dest=td/Path(source).name
        if Path(source).name=='r3_formal_dev_successor.py': source=str(refs['guard_controller']);h=c['guard_controller']['sha256']
        require(not dest.exists(),'duplicate tool basename');shutil.copyfile(source,dest)
        require(sha(dest)==h,'copied tool changed');mapping[next(k for k in tp['tools'] if Path(k).name==dest.name)]=str(dest)
    p.update(out=str(out),run='r3_runs/'+root.name+'/evaluation',container=c['container'],spec=str(out/'plan.json'),
        spec_sha256=sha(out/'plan.json'),launcher=mapping[tp['launcher']],resource_adapter=mapping[tp['resource_adapter']])
    p['tools']={mapping[f]:sha(mapping[f]) for f in tp['tools']};p['files']=dict(p['tools']);p['adapter']=p['resource_adapter']
    p['successor_guard']={'identity_mode':'sha256_raw','controller':mapping[tp['successor_guard']['controller']],
        'training_evidence':pin(mapping[tp['successor_guard']['training_evidence']['path']]),'schedule':c['schedule'],
        'predecessor_kind':'evaluation','previous_evaluation':{'execution':c['previous_execution'],'original_spec':c['previous_original_spec'],'derivation':c['previous_derivation']},
        'previous_role':read(previous['spec'])['training_variant']['formal_role_identity']['role'],'target_node':target,'training_role':role}
    write(out/'execution.json',p)
    guard={'schema':'r3-formal-dev-successor-v1','execution':pin(out/'execution.json'),'state_root':str(root/'guard-state'),
        'wake_source':pin(td/'r3_cpu_report_queue.py'),
        'poll_interval_seconds':600,'test_read':False,'scientific_acceptance':False,
        'event_wake_paths':[str(refs['previous_execution'].parent/n) for n in ['ENGINEERING_EVAL_EXIT.json','attempts/1/RELEASE.json','attempts/1/SUPERVISOR_DONE.json']]}
    guard['config_identity']=hashlib.sha256((json.dumps(guard,sort_keys=True,indent=2)+'\n').encode()).hexdigest()
    write(root/'CONFIG.json',guard);write(root/'CONFIG-PIN.json',pin(root/'CONFIG.json'))
    job=q['jobs'][0];job.update(eval_out=str(out),output=str(out/'results/selection_report.json'),plan=str(out/'plan.json'),
        plan_sha256=sha(out/'plan.json'),execution=str(out/'execution.json'),execution_sha256=sha(out/'execution.json'))
    q['event_wake_paths']=[str(out/n) for n in ['ENGINEERING_EVAL_EXIT.json','attempts/1/SUPERVISOR_DONE.json']]
    write(root/'cpu/queue.json',q)
    module(p['successor_guard']['controller']).verify(root/'CONFIG.json',sha(root/'CONFIG.json'))
    module(q['controller']).verify(root/'cpu/queue.json',sha(root/'cpu/queue.json'))
    for key,ref in c.items():
        if isinstance(ref,dict):pinned(ref)
    proof={'schema':'r3-formal-dev-guard-derivation-v1','configuration':{'path':str(path),'sha256':config_pin},
        'old_execution':c['execution'],'old_spec':pin(refs['execution'].parent/'plan.json'),'new_execution':pin(out/'execution.json'),
        'new_spec':pin(out/'plan.json'),'template':c['template_config'],'source_map':mapping,
        'changes_only':['results/identity output paths','reviewed evaluation-edge guard and registered predecessor binding'],
        'source_closure_unchanged':True,'test_read':False,'scientific_acceptance':False,'launch_authorized':False}
    write(root/'DERIVATION.json',proof)
    facts={'status':'PREPARED_PENDING_INDEPENDENT_EXACT_REVIEW','role':role,'chip':p['chip'],'root':str(root),
        'config':pin(root/'CONFIG.json'),'config_identity':guard['config_identity'],'execution':pin(out/'execution.json'),
        'cpu_queue':pin(root/'cpu/queue.json'),'derivation':pin(root/'DERIVATION.json'),
        'guard_controller':pin(p['successor_guard']['controller']),'launch_authorized':False,'test_read':False,'scientific_acceptance':False}
    write(root/'PREPARATION.json',facts);return facts

def main():
    a=argparse.ArgumentParser();a.add_argument('op',choices=['verify','prepare']);a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);v=a.parse_args()
    if v.op=='verify':inspect(v.config,v.sha256);print('GUARD_PREPARATION_CONFIG_VERIFIED')
    else:print(json.dumps(prepare(v.config,v.sha256),indent=2))
if __name__=='__main__':main()
