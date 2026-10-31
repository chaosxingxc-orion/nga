"""Host-175 detached final-test supervisor; requires actual reviewed inputs.

Never selects FINAL or creates approval. Observational uncertainty retains the
same container and device ownership. Missing post-launch container is not an
invitation to retry. Scripts monitor without waking a model.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace


def sibling(name):
    p=Path(__file__).with_name(name+'.py');s=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

A=sibling('r3_final_admission');K=sibling('r3_final_container')
R=sibling('r3_resource_adapter');D=sibling('r3_final_driver')


def observe(spec,container_id,digest,sleep=time.sleep):
    """Retry only absent/failed observations; definite identity mismatch fails."""
    while True:
        try:
            value=R.docker_inspect(spec['name'])
            if value is None:raise RuntimeError('retained container missing')
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
            D.atomic(digest,{'utc':D.utc(),'state':'observation_unknown','container_id':container_id,
                'action':'retry_same_container_without_restart_or_release','error':str(error)[:200]})
            sleep(30);continue
        return K.verify_observation(spec,value,container_id)


def resource_args(plan,pin,spec,directory,operation):
    return SimpleNamespace(alloc=K.ALLOCATION,run='final-test/'+pin,chip=plan['chip'],
        owner='R3 final test',purpose=plan['arm']+' calibration/test',container=spec['name'],
        claim=str(directory/'CLAIM.json'),proof=str(directory/(operation.upper()+'.json')))


def supervise(plan_path,pin,review,attempt):
    A.require(socket.gethostname()=='k8s-node1','final supervisor requires host175')
    plan_path=A.C.safe(plan_path);plan=json.loads(plan_path.read_text())
    A.verify(plan,pin,review)
    root=A.C.safe(plan['closure']['root'])
    A.require(Path(__file__).resolve()==root/'r3_code/r3_final_supervisor.py','supervisor outside frozen closure')
    image=subprocess.check_output(['docker','image','inspect',plan['image'],'--format','{{.Id}}'],text=True).strip()
    A.require(image==plan['image'],'actual image differs')
    spec=K.contract(plan,str(plan_path),pin,review,attempt)
    out=A.C.safe(plan['out']);out.mkdir(parents=True,exist_ok=True)
    lock=os.open(A.C.safe(out/'final-supervisor.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=A.C.safe(out/'supervisor-attempts'/str(attempt));directory.mkdir(parents=True,exist_ok=True)
        digest=directory/'digest.json';intent=directory/'LAUNCH_INTENT.json';receipt_path=directory/'LAUNCH_RECEIPT.json'
        command=K.command(spec)
        expected_intent={'plan_sha256':pin,'review':review,'attempt':attempt,'command':command}
        observed=R.docker_inspect(spec['name'])
        if observed is None:
            A.require(not intent.exists() and not receipt_path.exists(),
                      'launch was attempted but retained container is absent; do not relaunch')
            A.require(not (out/'final-attempts'/str(attempt)).exists(),'driver attempt already exists')
            if attempt>1:
                prior=out/'supervisor-attempts'/str(attempt-1)
                A.require((prior/'RELEASE.json').exists() and (prior/'DONE.json').exists(),
                          'prior attempt not exited/released')
                previous=json.loads((prior/'DONE.json').read_text())
                A.require(previous.get('publication_complete') is False,'completed final run cannot restart')
            else:
                A.require(not (out/'FINAL_EVAL_EXIT.json').exists(),'earlier terminal requires next attempt')
            A.require(not R.live_chip_conflict(plan['chip'],spec['name']),'device has live owner')
            R.claim(resource_args(plan,pin,spec,directory,'claim'))
            # Revalidate after resource acquisition and immediately before test
            # mounts become visible. A failure retains the claim for inspection.
            A.verify(plan,pin,review)
            D.atomic(intent,expected_intent)
            D.atomic(directory/'LAUNCH_SPEC.json',spec)
            try:
                subprocess.run(command,check=True,timeout=90,capture_output=True,text=True)
            except (subprocess.SubprocessError,OSError) as error:
                D.atomic(digest,{'utc':D.utc(),'state':'launch_observation_uncertain',
                    'error':str(error)[:200],'action':'observe_same_name_without_retry'})
            # Even if docker run timed out, do not send it again. Wait for the
            # exact retained container, validating the complete contract.
            observed=observe(spec,None,digest)
            D.atomic(receipt_path,{'id':observed['Id'],'plan_sha256':pin,'review':review})
        else:
            A.require(intent.exists() and json.loads(intent.read_text())==expected_intent,'container has no matching launch intent')
            A.require((directory/'CLAIM.json').exists(),'existing container lacks claim evidence')
            receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else None
            observed=K.verify_observation(spec,observed,receipt['id'] if receipt else None)
            if receipt is None:D.atomic(receipt_path,{'id':observed['Id'],'plan_sha256':pin,'review':review})
        cid=observed['Id']
        while observed['State']['Status'] not in ('exited','dead'):
            D.atomic(digest,{'utc':D.utc(),'state':'running','container_id':cid,'scientific_acceptance':False})
            time.sleep(30)
            observed=observe(spec,cid,digest)
        with (directory/'container.log').open('wb') as f:
            subprocess.run(['docker','logs',cid],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=30)
        driver_directory=A.C.safe(out/'final-attempts'/str(attempt));driver_directory.mkdir(parents=True,exist_ok=True)
        marker_path=driver_directory/'EXIT.json'
        marker=json.loads(marker_path.read_text()) if marker_path.exists() else None
        terminal=K.reconcile_exit(observed,marker,plan_sha256=pin,attempt=attempt)
        if marker is None:
            D.atomic(marker_path,terminal);D.atomic(out/'FINAL_EVAL_EXIT.json',terminal)
        # release() independently re-observes actual exit and device conflicts.
        R.release(resource_args(plan,pin,spec,directory,'release'))
        D.atomic(directory/'DONE.json',terminal)
        D.atomic(digest,{'utc':D.utc(),'state':'released','terminal':terminal})
        return terminal
    finally:os.close(lock)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('start','supervise'))
    parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--review',required=True);parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--attempt',required=True,type=int);args=parser.parse_args()
    review={'path':args.review,'sha256':args.review_sha256}
    if args.action=='supervise':
        print(json.dumps(supervise(args.plan,args.sha256,review,args.attempt),indent=2))
    else:
        A.require(socket.gethostname()=='k8s-node1','must start on host175')
        plan=json.loads(A.C.safe(args.plan).read_text());A.verify(plan,args.sha256,review)
        out=A.C.safe(plan['out']);out.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'supervise',*sys.argv[2:]]
        with (out/'supervisor.log').open('ab',buffering=0) as log:
            process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        D.atomic(out/'SUPERVISOR_RECEIPT.json',{'pid':process.pid,'command':cmd,'container_started':False})
        print(json.dumps({'pid':process.pid,'container_started':False}))
