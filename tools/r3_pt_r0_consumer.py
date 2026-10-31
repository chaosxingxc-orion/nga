#!/usr/bin/env python3
"""Verified CPU PT/R0 B-4 consumer; no scoring, allocation or test admission.

Config r3-pt-r0-consumer-config-v1 binds r0_preparation, r0_execution,
pt_closure (manifest.json), base_inventory as {path,sha256}; tools maps absolute
consumer/helper paths to SHA256. R0 sources are rebuilt before PT metrics.
Retained release receipts are checked here; live Docker observation belongs to
the producer supervisor. Each invocation runs in a fresh CPU process.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
TOOLS = {'r3_pt_r0_consumer.py', 'r3_pt_r0_report.py', 'r3_model_inventory.py',
         'r3_r0_report.py', 'r3_r0_prepare.py', 'r0rescore_verify.py'}


def require(ok, why):
    if not ok: raise ValueError(why)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p


def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def load(path): return json.loads(safe(path).read_text())
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def descriptor(path): return {'path':str(path),'sha256':sha(path)}


def artifact(entry):
    require(set(entry)=={'path','sha256'},'artifact descriptor differs')
    require(sha(entry['path'])==entry['sha256'],'artifact pin differs')
    return load(entry['path'])


def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def config(path,pin):
    d=artifact({'path':str(path),'sha256':pin})
    require(d.get('schema')=='r3-pt-r0-consumer-config-v1','consumer schema differs')
    files=d['tools']; require(len(files)==len(TOOLS) and {Path(p).name for p in files}==TOOLS,'consumer tool inventory differs')
    for p,h in files.items(): require(sha(p)==h,'consumer tool changed')
    require(str(Path(__file__).absolute()) in files,'consumer outside pinned tools')
    by_name={Path(p).name:Path(p) for p in files}
    require(by_name['r3_pt_r0_report.py'].parent==by_name['r3_model_inventory.py'].parent,'report inventory helper outside pinned siblings')
    for key in ('r0_preparation','r0_execution','pt_closure','base_inventory'):artifact(d[key])
    return d,by_name


def release(run,execution):
    """Validate recorded real-exit evidence, not merely a successful global marker."""
    require(execution.get('out')==str(run) and execution.get('schema')=='r3-engineering-posttrain-execution-v1'
            and execution.get('test_read') is False and execution.get('scientific_acceptance') is False,'execution scope differs')
    marker=load(run/'ENGINEERING_EVAL_EXIT.json');number=marker.get('attempt')
    require(type(number) is int and number>0 and type(marker.get('exit_code')) is int and marker['exit_code']==0,'successful producer terminal required')
    attempt=run/'attempts'/str(number)
    require(load(attempt/'EXIT.json')==marker,'attempt terminal differs')
    proof=load(attempt/'RELEASE.json');launch=load(attempt/'LAUNCH_RECEIPT.json')
    require(proof.get('container_id')==launch.get('id') and isinstance(launch.get('id'),str) and bool(launch['id'])
            and type(proof.get('exit_code')) is int and proof['exit_code']==0
            and proof.get('chip')==execution['chip'] and proof.get('run')==execution['run']
            and proof.get('scientific_acceptance') is False,'released container evidence differs')
    receipt=load(run/'SUPERVISOR_RECEIPT.json');cmd=receipt.get('command')
    require(isinstance(cmd,list) and len(cmd)==10 and Path(cmd[0]).name.startswith('python') and cmd[1:]==[
        '-P',execution['launcher'],'supervise','--plan',str(run/'execution.json'),
        '--sha256',sha(run/'execution.json'),'--attempt',str(number)],'latest supervisor identity differs')
    return {str(p):sha(p) for p in (run/'ENGINEERING_EVAL_EXIT.json',attempt/'EXIT.json',attempt/'RELEASE.json',attempt/'LAUNCH_RECEIPT.json',run/'SUPERVISOR_RECEIPT.json')}


def code_map(mounts,files):
    result={}
    for m in mounts:
        require(m.get('readonly') is True,'writable scientific code')
        root=safe(m['source']);folder=Path(m['destination']).name
        require(folder in ('r3_code','r0_code','r1_code'),'unexpected code destination')
        for p in root.rglob('*'):
            safe(p)
            if p.is_dir():continue
            require(p.is_file() and files.get(str(p))==sha(p),'unbound scientific source')
            key=str(Path(folder)/p.relative_to(root));require(key not in result,'duplicate code mount');result[key]=sha(p)
    return result


def pt_execution(run,pin,closure):
    execution=artifact({'path':str(run/'execution.json'),'sha256':pin})
    require(load(run/'QUEUE_EXECUTION_PIN.json')=={'sha256':pin},'producer queue pin differs')
    for p,h in execution['tools'].items():require(sha(p)==h,'producer launcher dependency changed')
    require(execution['launcher'] in execution['tools'],'unbound producer launcher')
    L=module(execution['launcher'],'pt_producer_launcher');L.verify(run/'execution.json',pin)
    spec=artifact({'path':execution['spec'],'sha256':execution['spec_sha256']})
    require(spec.get('evaluation_profile')=='track_t_pt_r0','PT R0 profile required')
    require(closure.get('evaluation_profile')=='track_t_pt_r0','PT closure profile differs')
    require(spec['code_mounts']==closure['mounts'] and set(spec['readonly_data_mounts'])==set(closure['data']),'PT closure mounts differ')
    for p,h in closure['data'].items():require(spec['files'].get(p)==h and sha(p)==h,'PT data closure differs')
    expected={x['snapshot']:x['sha256'] for x in closure['code'].values()}
    actual={str(p):sha(p) for m in closure['mounts'] for p in safe(m['source']).rglob('*') if p.is_file()}
    require(actual==expected and all(spec['files'].get(p)==h for p,h in expected.items()),'PT scientific closure differs')
    return execution,spec,release(run,execution)


def evaluate(run,pin,cfg,names):
    R=module(names['r3_r0_report.py'],'pt_r0_source_report');P=module(names['r3_r0_prepare.py'],'pt_r0_source_prepare')
    PT=module(names['r3_pt_r0_report.py'],'pt_b4_library')
    prep=artifact(cfg['r0_preparation']);P.validate(cfg['r0_preparation']['path'],cfg['r0_preparation']['sha256'])
    closure=artifact(cfg['pt_closure']);execution,spec,release_pins=pt_execution(run,pin,closure)
    r0_execution=artifact(cfg['r0_execution']);r0=Path(cfg['r0_execution']['path']).parent
    require(Path(cfg['r0_execution']['path']).name=='execution.json','R0 execution path differs')
    R.verify_execution(r0,cfg['r0_execution']['sha256'],prep);release_pins.update(release(r0,r0_execution))
    R.verify_code_record(r0,prep)
    r0_spec=artifact({'path':r0_execution['spec'],'sha256':r0_execution['spec_sha256']})
    require(code_map(spec['code_mounts'],spec['files'])==code_map(r0_spec['code_mounts'],r0_spec['files']),'PT/R0 executed scientific code differs')
    require(spec['readonly_data_mounts']==r0_spec['readonly_data_mounts'] or set(spec['readonly_data_mounts'])==set(r0_spec['readonly_data_mounts']),'PT/R0 data population differs')
    source_paths=[r0/'instruct/report.json',r0/'R0RESCORE_COMPLETE.json',r0/'R0RESCORE_VERIFIED.json',
                  run/'results/SCORING_RECEIPT.track_t_pt_r0.json',Path(spec['training'])/'manifest.json',
                  Path(spec['training'])/'plan.json',run/'plan.json',Path(r0_execution['spec'])]
    source_pins={str(p):sha(p) for p in source_paths}
    deps=R.frozen_modules(prep)
    V=module(names['r0rescore_verify.py'],'pt_r0_verifier')
    baseline,statuses=R.rebuild(r0,prep,deps)
    checked=V.check(str(r0),report_override=baseline,expected_execution_sha256=cfg['r0_execution']['sha256'])
    require(not checked['problems'] and checked['records_needed_R0']==102654,'R0 source verifier refused')
    require(canonical(load(r0/'instruct/report.json'))==canonical(baseline),'R0 published report differs from source reconstruction')
    complete=load(r0/'R0RESCORE_COMPLETE.json');verified=load(r0/'R0RESCORE_VERIFIED.json')
    require(complete.get('exit_code')==0 and complete.get('run_of_record') is True
            and complete.get('execution_sha256')==cfg['r0_execution']['sha256']
            and complete.get('preparation_sha256')==cfg['r0_preparation']['sha256']
            and complete.get('report_sha256')==sha(r0/'instruct/report.json')
            and complete.get('verified_sha256')==sha(r0/'R0RESCORE_VERIFIED.json')
            and not verified.get('problems') and verified.get('cpu_report_sha256')==sha(r0/'instruct/report.json'),'R0 completion bindings differ')
    receipt=load(run/'results/SCORING_RECEIPT.track_t_pt_r0.json')
    contract={'model':receipt['header']['model'],'base_model':baseline['header']['model'],
        'data':closure['data'],'training_plan':descriptor(Path(spec['training'])/'plan.json'),
        'base_inventory':cfg['base_inventory'],'pt_scoring_spec':descriptor(run/'plan.json'),
        'r0_scoring_spec':descriptor(r0/r0_execution['spec'])}
    require(contract['training_plan']['sha256']==spec['training_variant']['training_plan_sha256'],'PT training plan differs')
    result=PT.rebuild(run,contract,deps,baseline,PT.canonical_sha(baseline))
    # Recheck all mutable bindings after lengthy CPU reconstruction.
    require(sha(run/'execution.json')==pin,'PT execution changed during report')
    for p,h in {**release_pins,**source_pins}.items():require(sha(p)==h,'source/release evidence changed during report')
    P.validate(cfg['r0_preparation']['path'],cfg['r0_preparation']['sha256'])
    result['consumer_verification']={'run':str(run),'r0_source_reconstructed':True,'pt_execution_sha256':pin,
        'r0_execution_sha256':cfg['r0_execution']['sha256'],'release_evidence':release_pins,'source_evidence':source_pins,
        'r0_report_sha256':sha(r0/'instruct/report.json'),'scope':'source reconstruction and recorded release evidence; live Docker observation remains producer responsibility'}
    result['limitations']=['No formal eligibility, selection finality or independent review granted.',
        'Per-seed diagnostics; both seeds required for arm-level claims.']
    return result


def publish(path,result):
    require(not path.exists(),'output already exists')
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            f.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.link(tmp,path)
        parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:os.unlink(tmp)


def execute(run,pin,config_path,config_pin,output):
    run,output=safe(run),safe(output)
    require(output==run/'results/PT_R0_REPORT.json','dedicated PT output required')
    cfg,names=config(config_path,config_pin)
    with (run/'pt-r0-report.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not output.exists(),'output already exists')
        result=evaluate(run,pin,cfg,names)
        config(config_path,config_pin)
        result['consumer_verification']['config_sha256']=config_pin
        result['consumer_verification']['run']=str(run)
        publish(output,result)
    return {'output':str(output),'sha256':sha(output),'scientific_acceptance':False,'test_read':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','execution-sha256','config','config-sha256','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(execute(a.run,a.execution_sha256,a.config,a.config_sha256,a.output)))


if __name__=='__main__':main()
