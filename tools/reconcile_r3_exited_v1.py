#!/usr/bin/env python3
"""Retained-only R3 DEV/control failed lifecycle reconciliation; never launches."""
import argparse,contextlib,fcntl,hashlib,json,os,socket,types
from pathlib import Path

def need(ok,why):
    if not ok:raise ValueError(why)
def raw(path):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in [p,*p.parents]),'unsafe path');return p.read_bytes()
def sha(path):return hashlib.sha256(raw(path)).hexdigest()
def exact(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def pinned(ref):
    need(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'pin differs');return json.loads(raw(ref['path']))
def module(ref):
    b=raw(ref['path']);need(hashlib.sha256(b).hexdigest()==ref['sha256'],'source differs');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(b,ref['path'],'exec'),m.__dict__);return m

def absent_supervisor(receipt,launcher,plan):
    need(type(receipt['pid']) is int and receipt['pid']>0,'supervisor PID invalid')
    need(not Path('/proc',str(receipt['pid'])).exists(),'supervisor PID present')
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:args=(p/'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:continue
        need(not all(x.encode() in args for x in (launcher,plan,'supervise')),'replacement supervisor present')

def generation(a):return {k:a[k] for k in ('Id','Name','Image','Created','RestartCount','State')}
def container_check(c,p,a,command):
    need(a is not None and exact(generation(a),c['generation']),'container generation differs')
    st=a['State'];need(st['Status']=='exited' and st['Running'] is False and st['Restarting'] is False and type(st['ExitCode']) is int and st['ExitCode']!=0 and st['Pid']==0,'failed retained exit required')
    need(type(a['RestartCount']) is int and a['RestartCount']==0,'restart refused')
    need(a['Name']=='/'+p['container']+'-a1' and a['Image']==c['image'],'container identity differs')
    need(a['Config']['Cmd']==command[command.index(c['image'])+1:] and a['Config']['Entrypoint']==['python3'],'effective driver differs')
    need(a['HostConfig']['AutoRemove'] is False and a['HostConfig']['Privileged'] is False,'unsafe retention')
    devices=sorted((x['PathOnHost'],x['PathInContainer'],x['CgroupPermissions']) for x in a['HostConfig']['Devices'])
    need(devices==sorted(('/dev/'+x,'/dev/'+x,'rwm') for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci'+str(p['chip']))),'device differs')
    need(exact({k:a[k] for k in ('Config','HostConfig')},{k:c['effective_configuration'][k] for k in ('Config','HostConfig')}),'effective configuration differs')
    need(exact(sorted(a['Mounts'],key=lambda x:x['Destination']),sorted(c['effective_configuration']['Mounts'],key=lambda x:x['Destination'])),'mount observation changed')
    mounts=[]
    for i,x in enumerate(command):
        if x=='--mount':
            v=dict(y.split('=',1) for y in command[i+1].split(',') if '=' in y);mounts.append((v['src'],v['dst'],'readonly' not in command[i+1].split(',')))
    need(sorted(mounts)==sorted((x['Source'],x['Destination'],x['RW']) for x in a['Mounts']),'command mounts differ')

def load_configuration(path,pin):
    need(sha(path)==pin,'configuration changed');c=json.loads(raw(path))
    need(c['schema']=='reconcile-r3-retained-exit-v1' and c['attempt']==1 and type(c['attempt']) is int and c['scientific_acceptance'] is False and c['test_read'] is False,'reconciliation scope differs')
    need(c['implementation']['path']==str(Path(__file__).resolve()) and sha(__file__)==c['implementation']['sha256'],'implementation differs')
    need(socket.gethostname()=='k8s-node1','host175 only');p=pinned(c['plan']);out=Path(p['out']);a=out/'attempts/1'
    need(p['test_read'] is False and p['scientific_acceptance'] is False and p['run']==str(out.relative_to('/mnt/cephfs/xingchao/experiments/jev')),'plan scope differs')
    need(type(p['chip']) is int and 0<=p['chip']<8,'invalid chip')
    refs=c['receipts'];need(set(refs)=={'claim','launch_spec','launch_receipt','supervisor'},'receipt set differs')
    paths={'claim':a/'CLAIM.json','launch_spec':a/'LAUNCH_SPEC.json','launch_receipt':a/'LAUNCH_RECEIPT.json','supervisor':out/'SUPERVISOR_RECEIPT.json'}
    for k,v in paths.items():need(refs[k]['path']==str(v),'receipt path differs')
    receipts={k:pinned(v) for k,v in refs.items()};L=module(c['launcher']);R=module(c['resource'])
    need(p['launcher']==c['launcher']['path'] and p.get('tools',p.get('files',{}))[p['launcher']]==c['launcher']['sha256'],'launcher plan binding differs')
    if c['kind']=='dev':
        need(p['schema']=='r3-engineering-posttrain-execution-v1' and p['resource_adapter']==c['resource']['path'] and p['tools'][p['resource_adapter']]==c['resource']['sha256'],'DEV interface differs')
        spec=pinned(c['spec']);need(p['spec']==c['spec']['path'] and p['spec_sha256']==c['spec']['sha256'],'DEV spec differs')
        plan_pin=c['plan']['sha256'];cmd=L.docker_command(p,spec,c['plan']['path'],plan_pin,1);terminal=out/'ENGINEERING_EVAL_EXIT.json'
        need(receipts['launch_spec']=={'command':cmd,'sha256':plan_pin} and receipts['launch_receipt']=={'id':c['generation']['Id'],'image':c['image'],'sha256':plan_pin},'DEV launch binding differs')
    elif c['kind']=='control':
        need(p['schema']=='r3-formal-k1-plan-v1' and p['control_arm']=='K1-PT' and p['seed']==2 and p['adapter']==c['resource']['path'] and p['files'][p['adapter']]==c['resource']['sha256'],'control interface differs')
        plan_pin=L.identity(p);need(plan_pin==c['canonical_plan_sha256'],'canonical identity differs');cmd=L.docker_command(p,c['plan']['path'],1);terminal=out/'TRAIN_EXIT.json'
        need(receipts['launch_spec']=={'command':cmd,'plan_sha256':plan_pin} and receipts['launch_receipt']=={'id':c['generation']['Id'],'image':c['image'],'plan_sha256':plan_pin},'control launch binding differs')
    else:raise ValueError('unsupported exact schema')
    need(c['image']==L.IMAGE,'image differs');cl=receipts['claim']
    need(cl['schema']=='r3-resource-claim-v1' and cl['run']==p['run'] and exact(cl['chip'],p['chip']) and cl['allocation']==p['allocation'] and type(cl.get('successor_precondition')) is dict,'guarded claim differs')
    svc=receipts['supervisor'];args=svc['command']
    if c['kind']=='dev':
        need(args[1:]==['-P',p['launcher'],'supervise','--plan',c['plan']['path'],'--sha256',plan_pin,'--attempt','1'],'supervisor command differs')
    else:
        ctl=module(c['supervisor_controller']);cfg=pinned(c['supervisor_config']);ctl.verify_controller(c['supervisor_config']['path'],c['supervisor_config']['sha256'])
        job=ctl.by_id(cfg,'pt_seed2');need(job['plan']==c['plan']['path'] and job['raw_sha256']==c['plan']['sha256'] and job['canonical_sha256']==plan_pin,'controller job differs')
        activation=pinned(c['activation']);intent=pinned(c['start_intent'])
        expected=[args[0],'-B','-P','-c',ctl.PINNED_EXEC,c['supervisor_controller']['path'],c['supervisor_controller']['sha256'],'supervise','--config',c['supervisor_config']['path'],'--sha256',c['supervisor_config']['sha256'],'--activation',c['activation']['path'],'--activation-sha256',c['activation']['sha256'],'--job','pt_seed2']
        need(args==expected and intent['command']==expected and intent['config_sha256']==c['supervisor_config']['sha256'],'controller supervisor command differs')
        need(c['start_intent']['path']==str(Path(cfg['state_root'])/'pt_seed2.START_INTENT.json'),'intent path differs')
    return c,p,a,terminal,receipts,cmd,R,plan_pin

def run(path,pin,execute=False,review=None):
    c,p,a,terminal,receipts,cmd,R,plan_pin=load_configuration(path,pin);out=Path(p['out']);name=p['container']+'-a1';original=R.docker_inspect
    targets=[terminal,a/'EXIT.json',a/'RELEASE.json',a/'RELEASE.json.intent',a/'SUPERVISOR_DONE.json']
    def missing():
        for t in targets:
            need(not t.exists() and not t.with_name(t.name+'.pending').exists() and not t.with_suffix(t.suffix+'.tmp').exists() and not list(t.parent.glob('.'+t.name+'.*.pending')),'partial transaction refused')
    def check(n):
        need(n==name,'unexpected container');load_configuration(path,pin);missing();absent_supervisor(receipts['supervisor'],p['launcher'],c['plan']['path']);
        if c['kind']=='control':absent_supervisor(receipts['supervisor'],c['supervisor_controller']['path'],'pt_seed2')
        actual=original(n);container_check(c,p,actual,cmd);return actual
    lockpath=out/'supervisor.lock';need(lockpath.exists() and not lockpath.is_symlink(),'original lock missing')
    with lockpath.open('r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);check(name);need(not R.live_chip_conflict(p['chip'],None),'live device holder')
        with R.locked(p['allocation']):
            ledger=R.load(p['allocation']);R.validate_doc(ledger);need(exact([x for x in ledger['allocation'] if x['chip']==p['chip']],[receipts['claim']['entry']]) and not any(x['chip']==p['chip'] for x in ledger['free']),'claim generation differs')
        if not execute:return {'status':'VERIFIED_READ_ONLY','config_sha256':pin,'scientific_acceptance':False}
        need(review is not None,'independent review required');r=pinned(review);need(r.get('verdict')=='PASS' and r.get('approved_config_sha256')==pin and r.get('release_authorized') is True and r.get('scientific_acceptance') is False,'review scope differs')
        R.docker_inspect=check
        def during_release():
            for t in [terminal,a/'EXIT.json',a/'RELEASE.json',a/'SUPERVISOR_DONE.json']:need(not t.exists(),'terminal appeared during release')
        missing=during_release
        R.release(types.SimpleNamespace(alloc=p['allocation'],run=p['run'],chip=p['chip'],container=name,container_id=c['generation']['Id'],claim=str(a/'CLAIM.json'),proof=str(a/'RELEASE.json')))
        release=R.load(a/'RELEASE.json');need(release['claim_sha256']==c['receipts']['claim']['sha256'] and release['container_id']==c['generation']['Id'] and release['exit_code']==c['generation']['State']['ExitCode'],'release proof differs')
        term={'exit_code':c['generation']['State']['ExitCode'],'attempt':1,'source':'retained-container-exit','container_id':c['generation']['Id'],'plan_sha256':plan_pin,'raw_plan_sha256':c['plan']['sha256'],'runtime_terminal_present':False,'runtime_terminal_provenance':'missing; host reconstructed retained exit','scientific_acceptance':False,'test_read':False,'reconciliation_config_sha256':pin,'reconciliation_review':review,'release_sha256':sha(a/'RELEASE.json'),'reconciled_utc':R.utc()}
        R.write_atomic(a/'EXIT.json',term);R.write_atomic(terminal,term);R.write_atomic(a/'SUPERVISOR_DONE.json',{'exit_code':term['exit_code'],'source':'retained-container-reconciliation','reconciliation_config_sha256':pin,'container_id':term['container_id'],'scientific_acceptance':False})
        return {'status':'FAILED_GENERATION_RELEASED','scientific_acceptance':False,'automatic_retry':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','reconcile-exited']);p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);p.add_argument('--review');p.add_argument('--review-sha256');a=p.parse_args();print(json.dumps(run(a.config,a.sha256,a.op=='reconcile-exited',{'path':a.review,'sha256':a.review_sha256} if a.review and a.review_sha256 else None)))
if __name__=='__main__':main()
