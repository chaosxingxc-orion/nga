"""Finite QO/PT restart successors; only released retained tasks permit handoff.

This host-only controller prepares a new engineering restart generation from a
completed source, then delegates launch/observation to existing retained-job
machinery. Ambiguous preparation/start intents require repair, never a restart.
The 600-second script tick does not wake a model. No test or approval is produced.
"""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
S=module('r3_eval_successor')
Q=module('r3_posttrain_eval_queue')
P=module('r3_control_resume_prepare')
RESOURCE=module('r3_resource_adapter')
TOOLS={'r3_control_resume_successor.py','r3_eval_successor.py','r3_posttrain_eval_queue.py',
       'r3_control_resume_prepare.py','r3_resource_adapter.py','r3_formal_launcher.py',
       'r3_resume_evidence.py','r3_resume_contract.py'}
load=S.load;atomic=S.atomic;require=S.require



def predecessor_pin(job):
    """Bind a fixed execution or its pinned producer queue before observation.

    Dynamic executions are accepted only after the original queue has pinned
    their bytes, with spec/template/code identities tied back to that queue.
    No data or readout file is opened by this configuration check.
    """
    root=P.safe(job['after_eval_out']);execution=root/'execution.json'
    dynamic=job.get('after_queue')
    require((dynamic is not None) != ('after_execution_sha256' in job),
            'exactly one predecessor binding required')
    if dynamic is None:
        pin=job['after_execution_sha256']
        require(P.R.sha(execution)==pin,'predecessor execution changed')
    else:
        require(set(dynamic)=={'path','sha256','job_id'},'producer queue descriptor differs')
        qpath=P.safe(dynamic['path']);require(P.R.sha(qpath)==dynamic['sha256'],'producer queue changed')
        queue=load(qpath)
        require(queue.get('schema')=='r3-posttrain-queue-v1' and queue.get('test_read') is False
                and queue.get('scientific_acceptance') is False,'producer queue scope differs')
        rows=[j for j in queue['jobs'] if j['id']==dynamic['job_id']]
        require(len(rows)==1,'producer queue job differs');row=rows[0]
        require(row['out']==str(root) and row['chip']==job['chip'],'producer queue ownership differs')
        expected_tools={'r3_posttrain_eval_queue.py','r3_posttrain_eval_plan.py',
                        'r3_posttrain_eval_launcher.py','r3_resource_adapter.py'}
        require({Path(p).name for p in queue['tools']}==expected_tools,'producer tools differ')
        for filename,digest in queue['tools'].items():
            file=P.safe(filename)
            require(file.parent==qpath.parent and P.R.sha(file)==digest,'producer tool changed')
        closure_path=P.safe(queue['closure'])/'manifest.json'
        require(P.R.sha(closure_path)==queue['closure_sha256'],'producer closure changed')
        closure=load(closure_path)
        for entry in closure['code'].values():
            require(P.R.sha(P.safe(entry['snapshot']))==entry['sha256'],'scientific code changed')
        training=P.safe(row['training'])/'plan.json'
        require(P.R.sha(training)==row['training_plan_sha256'],'producer training plan changed')
        trained=load(training)
        require(trained.get('control_arm')=='K1-PT' and trained.get('seed')==3
                and trained.get('chip')==job['chip'],'dynamic predecessor must be PT seed3')
        if not execution.exists() or not (root/'QUEUE_EXECUTION_PIN.json').exists():return None
        pin=load(root/'QUEUE_EXECUTION_PIN.json')['sha256']
        require(P.R.sha(execution)==pin,'dynamic execution changed')
        prior=load(execution)
        require(prior.get('container')==row['container'] and prior.get('spec')==str(root/'plan.json'),
                'dynamic execution ownership differs')
        require(P.R.sha(root/'plan.json')==prior['spec_sha256'],'dynamic specification changed')
        spec=load(root/'plan.json');variant=spec['training_variant']
        require(spec.get('training')==row['training'] and variant.get('training_plan_sha256')==row['training_plan_sha256']
                and variant.get('arm')=='k1-pt' and variant.get('seed')==3,'dynamic training identity differs')
        require(spec.get('model')==trained['model'] and spec.get('adapter')==str(Path(row['training'])/'adapter')
                and spec.get('image_sha256')==trained['image_sha256'],'dynamic model identity differs')
        require(closure.get('evaluation_profile')=='track_t_pt_r0'
                and spec.get('evaluation_profile')=='track_t_pt_r0'
                and spec.get('test_read') is False and spec.get('scientific_acceptance') is False,
                'dynamic evaluation profile differs')
        replacements={'<FROZEN_BASE_MODEL>':trained['model'],'<COMPLETED_ADAPTER>':spec['adapter'],
                      '<FRESH_EVAL_OUTPUT>':str(root/'results'),'<FRESH_IDENTITY_CACHE>':str(root/'identity')}
        command=[replacements.get(x,x) for x in closure['command_template']]
        command[command.index('--arm')+1]='K1-PT'
        require(spec.get('command')==command and spec.get('code_mounts')==closure['mounts']
                and spec.get('readonly_data_mounts')==list(closure['data']), 'dynamic scoring template differs')
        dependencies={**closure['data'],**{v['snapshot']:v['sha256'] for v in closure['code'].values()}}
        require(all(spec['files'].get(p)==h for p,h in dependencies.items()),'dynamic scientific bindings differ')
        require({Path(p).name for p in prior['tools']}=={'r3_posttrain_eval_launcher.py','r3_resource_adapter.py'},
                'dynamic execution tools differ')
        for filename,digest in prior['tools'].items():
            file=P.safe(filename)
            require(file.parent==root/'execution-tools' and digest==queue['tools'][str(qpath.parent/file.name)]
                    and P.R.sha(file)==digest,'dynamic execution tool changed')
        require(prior['launcher']==str(root/'execution-tools/r3_posttrain_eval_launcher.py')
                and prior['resource_adapter']==str(root/'execution-tools/r3_resource_adapter.py'),
                'dynamic launcher identity differs')
    prior=load(execution)
    require(prior.get('chip')==job['chip'] and prior.get('out')==str(root)
            and prior.get('schema')=='r3-engineering-posttrain-execution-v1'
            and prior.get('scientific_acceptance') is False and prior.get('test_read') is False,
            'predecessor scope/chip differs')
    require(P.R.sha(execution)==pin,'predecessor changed during binding')
    if dynamic is not None:
        require(P.R.sha(qpath)==dynamic['sha256']
                and P.R.sha(closure_path)==queue['closure_sha256']
                and P.R.sha(training)==row['training_plan_sha256']
                and P.R.sha(root/'plan.json')==prior['spec_sha256']
                and load(root/'QUEUE_EXECUTION_PIN.json')['sha256']==pin,
                'dynamic predecessor changed during binding')
    return pin


def verify(path,pin):
    path=P.safe(path)
    require(P.R.sha(path)==pin,'control successor queue changed')
    doc=load(path)
    require(doc.get('schema')=='r3-control-resume-successor-v1'
            and doc.get('scientific_acceptance') is False and doc.get('test_read') is False
            and doc.get('interval_seconds')==600,'queue scope/cadence differs')
    require({Path(p).name for p in doc['tools']}==TOOLS,'successor tool inventory differs')
    require(str(Path(__file__).resolve()) in doc['tools'],'different successor executable')
    for filename,digest in doc['tools'].items():
        p=P.safe(filename)
        require(p.parent==HERE and P.R.sha(p)==digest,'successor tool changed')
    jobs=doc['jobs']
    require(isinstance(jobs,list) and jobs,'empty successor jobs')
    for field in ('id','out','source_plan','chip'):
        require(len({j[field] for j in jobs})==len(jobs),'duplicate successor '+field)
    for j in jobs:
        require(set(j) in ({'id','source_plan','source_pin','source_step','after_eval_out','after_execution_sha256','chip','out'},
                           {'id','source_plan','source_pin','source_step','after_eval_out','after_queue','chip','out'}), 'job fields differ')
        require(type(j['chip']) is int and j['chip'] in range(8),'invalid successor chip')
        require(type(j['source_step']) is int and j['source_step']==3000,'registered source step required')
        source=P.safe(j['source_plan']);out=P.safe(j['out']);previous=P.safe(j['after_eval_out'])
        require(source.name=='plan.json' and out!=source.parent and out!=previous
                and not out.is_relative_to(source.parent) and not source.parent.is_relative_to(out),
                'source/output overlap')
        plan=load(source)
        require(P.R.identity(plan)==j['source_pin'],'source plan changed')
        require(plan.get('control_arm') in ('K1-QO','K1-PT') and plan.get('seed')==2
                and plan.get('out')==str(source.parent),'source identity differs')
        predecessor_pin(j)
    return doc


def ready(job):
    """Both source and last chip predecessor need successful actual exits."""
    source=load(job['source_plan'])
    require(P.R.identity(source)==job['source_pin'],'source plan changed')
    origin=S.predecessor({'previous_kind':'training','previous_eval':source['out'],'chip':source['chip']})
    require(P.R.identity(load(job['source_plan']))==job['source_pin'],'source plan changed during observation')
    if origin is None:return {'status':'waiting_source_release'}
    if origin['exit_code']!=0:return {'status':'source_failed','source':origin}
    pin=predecessor_pin(job)
    if pin is None:return {'status':'waiting_predecessor_execution'}
    prior=Q.predecessor({'after_eval':job['after_eval_out'],'out':job['out'],'chip':job['chip']},RESOURCE)
    require(predecessor_pin(job)==pin,'predecessor execution changed during observation')
    if prior['status']!='predecessor_done':return prior
    return {'status':'ready','source':origin,'previous':prior}


def tick(job):
    out=P.safe(job['out'])
    intent=out.with_name(out.name+'.PREPARE_INTENT.json')
    prepared=out.with_name(out.name+'.PREPARED.json')
    if prepared.exists():
        require(intent.exists(),'prepared restart lacks preparation intent')
        record=load(prepared)
        require(record['job']==job and load(intent)['job']==job,'prepared successor job differs')
        result=record['result'];plan=load(result['plan'])
        require(result['plan']==str(out/'plan.json') and P.R.identity(plan)==result['plan_sha256']
                and plan['chip']==job['chip'] and plan['out']==str(out),'prepared restart identity differs')
        preparation=load(out/'PREPARATION.json');origin=load(out/'SOURCE.json')
        require(preparation['source_plan']==job['source_plan']
                and preparation['source_plan_pin']==job['source_pin']
                and origin['step']==job['source_step']
                and origin['checkpoint']==str(Path(job['source_plan']).parent/'ckpt'/f"step_{job['source_step']:06d}.pt"),
                'prepared restart source differs')
        require(predecessor_pin(job) is not None,'prepared predecessor execution missing')
        if not (out/'SUCCESSOR_START_INTENT.json').exists():
            evidence=ready(job)
            if evidence['status']!='ready':return evidence
        return S.tick({'next_execution':result['plan'],'next_sha256':result['plan_sha256'],
                       'next_kind':'training','previous_kind':'evaluation',
                       'previous_eval':job['after_eval_out'],'chip':job['chip']})
    if intent.exists() or out.exists():
        return {'status':'needs_repair','reason':'partial preparation; never overwrite or silently retry'}
    evidence=ready(job)
    if evidence['status']!='ready':return evidence
    source=load(job['source_plan']);checkpoint=Path(source['out'])/'ckpt'/f"step_{job['source_step']:06d}.pt"
    # A completed source lacking its registered checkpoint is an error, not a
    # reason to choose a different checkpoint or launch an untrained contract.
    checkpoint_pin=P.R.sha(checkpoint)
    atomic(intent,{'job':job,'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_pin,
                   'evidence':evidence,'utc_seconds':time.time()})
    P.prepare(job['source_plan'],job['source_pin'],str(checkpoint),checkpoint_pin,
              job['source_step'],str(out),job['chip'])
    prep=out/'PREPARATION.json'
    result=P.finalize(str(prep),P.R.sha(prep))
    require(result.get('deployable') is True and result.get('scientific_acceptance') is False
            and result.get('test_read') is False,'prepared scope differs')
    plan=load(result['plan'])
    subprocess.run([sys.executable,'-P',plan['launcher'],'verify','--plan',result['plan'],
                    '--sha256',result['plan_sha256']],capture_output=True,check=True,timeout=120)
    atomic(prepared,{'job':job,'result':result,'evidence':evidence})
    # Recheck immediately rather than adding a 10-minute dispatch delay.
    return tick(job)


def watch(path,pin):
    with (path.parent/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            doc=verify(path,pin);states={}
            for job in doc['jobs']:
                try:states[job['id']]=tick(job)
                except Exception as exc:
                    states[job['id']]={'status':'observation_or_preparation_uncertain','error':str(exc)[:300]}
            digest={'utc_seconds':time.time(),'jobs':states,'scientific_acceptance':False,'test_read':False}
            atomic(path.parent/'digest.json',digest)
            if all(x['status']=='handed_off' for x in states.values()):
                atomic(path.parent/'DONE.json',digest);return
            time.sleep(600)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('op',choices=('verify','start','watch'))
    ap.add_argument('--manifest',required=True);ap.add_argument('--sha256',required=True)
    args=ap.parse_args();path=P.safe(args.manifest);verify(path,args.sha256)
    if args.op=='verify':print('CONTROL_RESUME_SUCCESSOR_VERIFIED');return
    require(socket.gethostname()=='k8s-node1','host 175 only')
    if args.op=='watch':watch(path,args.sha256);return
    cmd=[sys.executable,'-P',str(Path(__file__).resolve()),'watch','--manifest',str(path),'--sha256',args.sha256]
    with (path.parent/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt=path.parent/'SERVICE.json'
        if receipt.exists():
            old=load(receipt)
            require(old['command']==cmd and S.process_matches(old),'prior controller absent; explicit repair required')
            print(json.dumps({'status':'ALREADY_LIVE','pid':old['pid']}));return
        intent=path.parent/'SERVICE_START_INTENT.json'
        require(not intent.exists(),'uncertain prior controller start; do not duplicate')
        atomic(intent,{'command':cmd,'utc_seconds':time.time()})
        with (path.parent/'service.log').open('ab') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        atomic(receipt,{'pid':proc.pid,'command':cmd})
        atomic(path.parent/'RELAUNCH.json',{'command':[sys.executable,'-P',str(Path(__file__).resolve()),
               'start','--manifest',str(path),'--sha256',args.sha256]})
        print(json.dumps({'status':'STARTED','pid':proc.pid}))


if __name__=='__main__':main()
