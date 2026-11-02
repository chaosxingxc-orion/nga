"""Detached, reviewed host175 BEV length-bucket DEV probe lifecycle. Never decides scientific acceptance."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import types


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def module(path,name):
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(Path(path).read_bytes(),str(path),'exec',dont_inherit=True),m.__dict__);return m


def runner(plan): return module(plan['code']['runner']['path'],'bev_runner')
def inspect(name):
    p=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    if p.returncode:
        if 'no such' in p.stderr.lower(): return None
        raise ValueError('Docker observation uncertain')
    return json.loads(p.stdout)[0]


def review(plan_path,pin,review_path,review_pin):
    require(sha(review_path)==review_pin,'review pin differs')
    r=load(review_path)
    require(r.get('approved_plan_sha256')==pin and r.get('activation_authorized') is True and
            r.get('scientific_acceptance') is False,'independent activation review required')
    require(r.get('scope') == 'train_derived_dev' and r.get('test_read') is False,
            'DEV probe review scope differs')
    require(r.get('attempts') == [1], 'only fresh attempt1 can be reviewed')
    d=load(plan_path);require(sha(__file__)==d['code']['host']['sha256'],'host changed')
    require(sha(plan_path)==pin and r.get('hashes',{}).get(str(plan_path))==pin, 'review plan binding differs')
    for group in ('code','inputs','model_files'):
        for item in d[group].values():
            require(sha(item['path'])==item['sha256'] and r.get('hashes',{}).get(item['path'])==item['sha256'],
                    'dependency outside exact review')
    require(r.get('expected_commands') == {str(a):expected_command(d,plan_path,pin,a) for a in r.get('attempts',[])}, 'exact launch commands not reviewed')
    if 'successor_guard' in d:
        e=d['successor_guard']['controller']
        require(sha(e['path'])==e['sha256'] and r.get('hashes',{}).get(e['path'])==e['sha256'],'guard controller outside review')
    return runner(d).verify(plan_path,pin)


def expected_command(plan,plan_path,pin,attempt):
    require(type(attempt) is int and attempt == 1, 'only fresh attempt1 is supported')
    command=['docker','run','-d','--name',plan['container']+'-a'+str(attempt),'--network','none','--shm-size','16g',
             '--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864',
             '--device','/dev/davinci_manager','--device','/dev/devmm_svm','--device','/dev/hisi_hdc',
             '--device','/dev/davinci'+str(plan['chip']),
             '-v','/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro']
    for name_env,value in plan['environment'].items():command+=['-e',name_env+'='+value]
    for mount in plan['mounts']:command+=['-v',mount['source']+':'+mount['destination']+(':ro' if mount['readonly'] else '')]
    for p in ['/usr/local/sbin','/etc/ascend_install.info']:
        command+=['-v',p+':'+p+':ro']
    command += [plan['image_sha256'],'python3','-B','-P',plan['code']['runner']['path'],
                'run','--plan',str(plan_path),'--sha256',pin,'--attempt',str(attempt)]
    return command


def supervise(args):
    plan=review(args.plan,args.sha256,args.review,args.review_sha256);R=runner(plan)
    require(type(args.attempt) is int and args.attempt in load(args.review).get('attempts',[]), 'attempt not reviewed')
    require(socket.gethostname()=='k8s-node1','host175 required')
    out=Path(plan['out']);host=out/'host_attempts'/str(args.attempt)
    with (out/'host.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        R.fresh_measurement(out,args.attempt)
        require(not (host/'CLAIM.json').exists(),'prior claim requires reconciliation')
        name=plan['container']+'-a'+str(args.attempt)
        require(inspect(name) is None,'container collision')
        ids=subprocess.check_output(['docker','ps','-q'],text=True,timeout=30).split()
        if ids:
            for d in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=30)):
                require(not any(x['PathOnHost']=='/dev/davinci'+str(plan['chip']) for x in d['HostConfig'].get('Devices',[])),'competing device container')
        adapter=[sys.executable,'-B','-P',plan['code']['resource']['path']]
        command=expected_command(plan,args.plan,args.sha256,args.attempt)
        require(command == load(args.review)['expected_commands'][str(args.attempt)], 'exact launch command differs')
        # Exclusive generation ownership and freshness are established before
        # the resource adapter can claim the chip. The runner checks again.
        R.reserve_measurement(out,args.sha256,args.attempt)
        claim=adapter+['claim','--alloc',plan['allocation'],'--run',plan['run'],'--chip',str(plan['chip']),
                      '--owner','BEV length-bucket DEV probe','--purpose','72 fixed TRAIN-derived DEV requests; exact outer-length-bucket equivalence and timing',
                      '--proof',str(host/'CLAIM.json')]
        if 'successor_guard' in plan:
            require(args.precondition == str(out/'SUCCESSOR_PRECONDITION.json') and sha(args.precondition)==args.precondition_sha256,'precondition binding differs')
            claim += ['--plan',args.plan,'--plan-sha256',args.sha256,'--precondition-sha256',args.precondition_sha256]
        subprocess.run(claim,check=True,capture_output=True,timeout=30)
        R.atomic(host/'LAUNCH_SPEC.json',{'command':command,'plan_sha256':args.sha256})
        result=subprocess.run(command,capture_output=True,text=True,timeout=60)
        if result.returncode:
            R.atomic(host/'LAUNCH_UNCERTAIN.json',{'rc':result.returncode,'stderr':result.stderr[-1000:]})
            raise ValueError('launch failed; retain claim for reconciliation')
        actual=inspect(name)
        expected_runner=command[command.index(plan['image_sha256'])+1:]
        require(actual and actual['Config']['Cmd']==expected_runner,'actual runner command differs')
        require(actual and actual['Image']==plan['image_sha256'] and not actual['HostConfig'].get('AutoRemove'),'launched container binding differs')
        R.atomic(host/'LAUNCH_RECEIPT.json',{'container_id':actual['Id'],'plan_sha256':args.sha256,'command':actual['Config']['Cmd']})
        while True:
            actual=inspect(name);require(actual is not None,'retained container missing')
            R.atomic(host/'heartbeat.json',{'utc_seconds':time.time(),'container_id':actual['Id'],'state':actual['State']['Status']})
            if actual['State']['Status']=='exited':break
            require(actual['State']['Status'] in ('created','running'),'container state uncertain')
            time.sleep(15)
        release=adapter+['release','--alloc',plan['allocation'],'--run',plan['run'],'--chip',str(plan['chip']),
                         '--container',name,'--container-id',actual['Id'],'--claim',str(host/'CLAIM.json'),'--proof',str(host/'RELEASE.json')]
        subprocess.run(release,check=True,capture_output=True,timeout=300)
        terminal=out/'attempts'/str(args.attempt)/'EXIT.json'
        rc=actual['State']['ExitCode'];valid=terminal.exists() and load(terminal).get('exit_code')==rc
        R.atomic(host/'EXIT.json',{'exit_code':rc if valid else 1,'container_exit_code':rc,'runner_terminal_matches':valid,
                                 'container_id':actual['Id'],'scientific_acceptance':False,'utc_seconds':time.time()})
        require(valid,'runner terminal missing or mismatched; resource released but result invalid')


def start(args):
    plan=review(args.plan,args.sha256,args.review,args.review_sha256);R=runner(plan)
    require(type(args.attempt) is int and args.attempt in load(args.review).get('attempts',[]), 'attempt not reviewed')
    require(socket.gethostname()=='k8s-node1' and args.attempt>=1,'host or attempt differs')
    out=Path(plan['out']);out.mkdir(parents=True,exist_ok=True)
    with (out/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        R.fresh_measurement(out,args.attempt)
        require(not os.path.lexists(out/'MEASUREMENT_OWNER.json'),'measurement already reserved; reconcile explicitly')
        host=out/'host_attempts'/str(args.attempt);host.mkdir(parents=True,exist_ok=False)
        command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'supervise','--plan',args.plan,
                 '--sha256',args.sha256,'--review',args.review,'--review-sha256',args.review_sha256,'--attempt',str(args.attempt)]
        if 'successor_guard' in plan:
            require(args.precondition == str(out/'SUCCESSOR_PRECONDITION.json') and sha(args.precondition)==args.precondition_sha256,'precondition binding differs')
            command += ['--precondition',args.precondition,'--precondition-sha256',args.precondition_sha256]
        R.atomic(host/'START_INTENT.json',{'command':command,'utc_seconds':time.time()})
        with (host/'supervisor.log').open('ab') as log:
            p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                               start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        R.atomic(host/'SERVICE.json',{'pid':p.pid,'command':command})
        print(json.dumps({'status':'supervisor_started','pid':p.pid,'attempt':args.attempt}))


def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=['start','supervise']);p.add_argument('--plan',required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--review',required=True);p.add_argument('--review-sha256',required=True)
    p.add_argument('--attempt',type=int,default=1);p.add_argument('--precondition');p.add_argument('--precondition-sha256');args=p.parse_args()
    try: return start(args) if args.op=='start' else supervise(args)
    except BaseException as error:
        if args.op=='supervise':
            d=load(args.plan);root=Path(d['out'])/'host_attempts'/str(args.attempt)
            R=runner(d); failure={'utc_seconds':time.time(),'error':str(error)[:1000],'scientific_acceptance':False,'exit_code':1,'status':'needs_reconciliation'}
            R.atomic(root/'SUPERVISOR_ERROR.json',failure)
            if not (root/'EXIT.json').exists():R.atomic(root/'EXIT.json',failure)
        raise


if __name__=='__main__':main()
