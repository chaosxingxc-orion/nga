#!/usr/bin/env python3
"""Independent E40 chip-1 release transaction; never launches a container."""
import argparse
import base64
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid
from contextlib import contextmanager

ROOT = Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
ALLOCATION = ROOT.parent / 'CHIP-ALLOCATION.json'
PLAN_HASHES = {'e40_lifetime_npu_openjev2_20261031_v3': '90721d6509df030a71ed012848f7a0b11ce31b7fd11d63c306fbaf90b223c3d9'}


EVIDENCE_HELPER_SHA256 = '12a5e895d6fa16df0506418dfbad0affe584cd06e62993a40bee0b4d86ee5b77'


def bootstrap_module(path, name, expected_sha256):
 """Authenticate helper bytes before execution, without importing that helper.

 The reviewed release executable pins this digest. The helper may not supply
 its own expected digest. Execute the bytes read from the authenticated file
 descriptor, never a subsequent path import (including Python bytecode caches).
 """
 path=Path(os.path.abspath(path))
 directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  for part in path.parts[1:-1]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
   os.close(directory);directory=child
  fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
  def identity(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
  with os.fdopen(fd,'rb') as stream:
   before=os.fstat(stream.fileno())
   if not stat.S_ISREG(before.st_mode) or before.st_size>8*2**20:
    raise ValueError('Invalid bootstrap helper file')
   raw=stream.read()
   if hashlib.sha256(raw).hexdigest()!=expected_sha256:
    raise ValueError('Bootstrap helper SHA256 differs')
   if identity(os.fstat(stream.fileno()))!=identity(before):
    raise ValueError('Bootstrap helper changed during read')
   current=os.stat(path.name,dir_fd=directory,follow_symlinks=False)
   if not stat.S_ISREG(current.st_mode) or identity(current)!=identity(before):
    raise ValueError('Bootstrap helper path changed during read')
 finally:os.close(directory)
 value=importlib.util.module_from_spec(importlib.util.spec_from_loader(name,loader=None))
 value.__file__=str(path)
 exec(compile(raw,str(path),'exec'),value.__dict__)
 return value


evidence=bootstrap_module(Path(__file__).with_name('e38_evidence.py'),
                          'e38_release_evidence',EVIDENCE_HELPER_SHA256)
require=evidence.require


@contextmanager
def exclusive_lock(path):
    """Open a lock without truncating or following a symlink."""
    path = Path(path)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink >= 1, 'Release lock is not a regular file')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try: fcntl.flock(fd, fcntl.LOCK_UN)
        finally: os.close(fd)


def encoded(value):
 # Exactly the frozen queue helper atomic JSON encoding.
 return json.dumps(value,indent=2,allow_nan=False).encode()


def digest(raw):return hashlib.sha256(raw).hexdigest()


def trusted_anchor(q, path, expected_sha256, review_path):
 # The digest is supplied by the trusted caller, outside mutable review/journal.
 require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}',expected_sha256),
         'A caller-pinned release anchor SHA256 is required')
 require(q.sha(path)==expected_sha256,'Trusted release anchor changed')
 anchor=q.load(path)
 require(anchor['schema']=='e40-resource-release-anchor-v1'
         and anchor['release_review_sha256']==q.sha(review_path),'Anchored release review changed')
 try:raw=base64.b64decode(anchor['allocation_before_bytes_b64'],validate=True)
 except Exception as exc:raise ValueError('Invalid anchored allocation bytes') from exc
 require(digest(raw)==anchor['allocation_before_sha256'],'Anchored allocation hash differs')
 json.loads(raw)
 return anchor,raw


def bind(plan_path, verification_request, review_path, q, prep, anchor_path, anchor_sha256):
 anchor,before_bytes=trusted_anchor(q,anchor_path,anchor_sha256,review_path)
 p=q.load(plan_path);ph=q.sha(plan_path);out=plan_path.parent
 require(out.parent==ROOT and PLAN_HASHES.get(out.name)==ph and p['out']==str(out)
         and p['physical_chip']==1 and p['candidate_batch_admission'] is False,'Unreviewed E40 release target')
 review=q.load(review_path);vout=verification_request.parent;r=q.load(verification_request)
 require(vout.parent==ROOT and r['schema']=='e40-detached-cpu-verify-v1'
         and r['out']==str(vout) and r['plan']==str(plan_path) and r['plan_sha256']==ph,'CPU request target differs')
 # All request bytes, including the independently reviewed CPU launcher, are fixed.
 q.frozen(r['files']);q.frozen(p['files'])
 require(review['cpu_verifier_tool_sha256']==q.sha(vout/'openjev_lifetime_verify_launch.py'),
         'CPU verifier executable review differs')
 for folder,key in [(out,'approved_plan_sha256'),(vout,'approved_request_sha256')]:
  launch_review=q.load(folder/'PARENT_REVIEW.json')
  require(launch_review['approved'] is True and launch_review[key]==q.sha(plan_path if folder==out else verification_request),
          'Exact parent launch approval differs')
 independent=q.load(out/'INDEPENDENT_REVIEW.json')
 require(independent['approved'] is True and independent['approved_plan_sha256']==ph
         and q.sha(independent['review_path'])==independent['review_sha256'],'Independent NPU approval differs')
 npu=q.inspect(p['container']);cpu=q.inspect(r['container'])
 nl=q.load(out/'LAUNCH_RECEIPT.json');cl=q.load(vout/'LAUNCH_RECEIPT.json')
 ns=q.load(p['container_spec']);q.binding(npu,ns,nl);cs=q.load(vout/'CPU_SPEC.json');q.binding(cpu,cs,cl)
 for actual,spec in [(npu,ns),(cpu,cs)]:
  require(not actual.get('HostConfig',{}).get('AutoRemove') and not spec['HostConfig'].get('AutoRemove'),'Retained container required')
 require(cs['HostConfig']['Devices']==[] and not q.devices(cpu) and not cs['HostConfig'].get('Privileged')
         and not cs['HostConfig'].get('DeviceRequests') and not cs['HostConfig'].get('DeviceCgroupRules')
         and not cs['HostConfig'].get('AutoRemove'),'CPU exposure/retention differs')
 for d in [npu,cpu]:require(d['State']['Status']=='exited' and d['State']['ExitCode']==0,'Container not exited/0')
 require(npu['Id']==r['npu_id'] and npu['State']['StartedAt']==r['npu_started_at']
         and npu['State']['FinishedAt']==r['npu_finished_at'],'NPU generation differs from CPU request')
 require(nl['plan_sha256']==ph and nl['wrapper_sha256']==q.sha(p['wrapper'])
         and nl['parent_review_sha256']==q.sha(out/'PARENT_REVIEW.json'),'NPU receipt differs')
 rh=q.sha(verification_request)
 require(cl['request_sha256']==rh and cl['wrapper_sha256']==q.sha(vout/'run.sh')
         and cl['parent_review_sha256']==q.sha(vout/'PARENT_REVIEW.json'),'CPU receipt differs')
 for folder in [out,vout]:
  require(re.fullmatch(r'rc=0 utc=\S+\n?',q.snapshot(folder/'EXIT').data.decode()),'Wrapper EXIT differs')
  require(not any((folder/n).exists() for n in ['FAILED_GENERATION.json','FAILURE.json']),'Failed generation normal release forbidden')
 nt=q.load(out/'COMPLETE.json');nr=q.load(out/'report.json');ct=q.load(vout/'COMPLETE.json');cr=q.load(vout/'report.json')
 require(nt['rc']==0 and nt['stage']=='completed' and nt['progress']==nt['total']==8
         and nt['plan_sha256']==ph and nt['output_sha256']==q.sha(out/'report.json')
         and nt['candidate_batch_admission'] is False and not nt.get('rejected_manifest'), 'NPU terminal differs')
 require(ct['rc']==0 and ct['request_sha256']==rh and ct['cpu_id']==cpu['Id']
         and ct['cpu_started_at']==cpu['State']['StartedAt']
         and ct['outputs']=={'report.json':q.sha(vout/'report.json')},'CPU terminal differs')
 gen=dict(container_id=npu['Id'],started_at=npu['State']['StartedAt'],launch_receipt_sha256=q.sha(out/'LAUNCH_RECEIPT.json'))
 require(q.load(out/'GENERATION.json')==gen==nr['generation']==cr['generation'],'NPU generation binding differs')
 require(cr['plan_sha256']==ph and cr['actual_exit']==0 and cr['finished_at']==npu['State']['FinishedAt']
         and cr['report_sha256']==q.sha(out/'report.json') and cr['terminal_sha256']==q.sha(out/'COMPLETE.json'),
         'Independent result binding differs')
 # Reconstruct controls again from all eight receipts, not only report equality.
 proto=prep.frozen_module(out/'openjev_lifetime_protocol.py','e40_release_protocol')
 verifier=prep.frozen_module(out/'openjev_lifetime_verify.py','e40_release_verify')
 prior=prep.frozen_module(out/'verify_openjev_path_trace.py','e40_release_prediction')
 items=proto.check_receipts(p,ph,q,prior.check_prediction,complete=True,generation=gen)
 expected=verifier.reconstruct(items)
 require(all(nr.get(k)==v and cr.get(k)==v for k,v in expected.items()),'Scientific reconstruction differs')
 for folder,key in [('items','receipt_manifest'),('attempts','attempt_manifest')]:
  require(nr[key]=={f.name:q.sha(f) for f in sorted((out/folder).iterdir())},'Receipt population differs')
 attestation=vout/'CPU_EXIT_BINDING.json'
 att=dict(request_sha256=rh,report_sha256=q.sha(vout/'report.json'),terminal_sha256=q.sha(vout/'COMPLETE.json'),
   receipt_sha256=q.sha(vout/'LAUNCH_RECEIPT.json'),exit_sha256=q.sha(vout/'EXIT'),container_id=cpu['Id'],
   started_at=cpu['State']['StartedAt'],finished_at=cpu['State']['FinishedAt'],actual_exit=0,devices=[])
 require(q.sha(attestation)==anchor['cpu_exit_binding_sha256'] and q.load(attestation)==att,'CPU post-exit attestation differs')
 require(review['schema']=='e40-resource-release-review-v1' and review['approved'] is True
   and review['approved_plan_sha256']==ph and review['verification_request_sha256']==rh
   and review['verification_report_sha256']==q.sha(vout/'report.json')
   and review['verification_terminal_sha256']==q.sha(vout/'COMPLETE.json')
   and review['accepted_exact_outputs'] is expected['exact_outputs']
   and review['accepted_review_flags']==expected['review_flags'] and review['candidate_batch_admission'] is False
   and review['release_tool_sha256']==q.sha(Path(__file__))
   and review['evidence_helper_sha256']==q.sha(Path(__file__).with_name('e38_evidence.py'))
   and review['cpu_exit_binding_sha256']==q.sha(attestation)
   and review['allocation_before_sha256']==anchor['allocation_before_sha256'],'Release approval omits binding or scientific flags')
 bindings=dict(plan_sha256=ph,verification_request_sha256=rh,verification_report_sha256=q.sha(vout/'report.json'),
   verification_terminal_sha256=q.sha(vout/'COMPLETE.json'),release_review_sha256=q.sha(review_path),
   release_tool_sha256=review['release_tool_sha256'],evidence_helper_sha256=review['evidence_helper_sha256'],
   cpu_verifier_tool_sha256=review['cpu_verifier_tool_sha256'],npu_container_id=npu['Id'],cpu_container_id=cpu['Id'],
   npu_started_at=npu['State']['StartedAt'],npu_finished_at=npu['State']['FinishedAt'],
   cpu_started_at=cpu['State']['StartedAt'],cpu_finished_at=cpu['State']['FinishedAt'],
   npu_exit_sha256=q.sha(out/'EXIT'),cpu_exit_sha256=q.sha(vout/'EXIT'),
   npu_report_sha256=q.sha(out/'report.json'),cpu_exit_binding_sha256=q.sha(attestation),
   accepted_exact_outputs=expected['exact_outputs'],accepted_review_flags=expected['review_flags'],candidate_batch_admission=False,
   trusted_anchor_sha256=anchor_sha256,approved_allocation_before_sha256=anchor['allocation_before_sha256'],
   approved_allocation_before_bytes_b64=base64.b64encode(before_bytes).decode())
 return p,bindings


def empty_now(q,prep):
 # Exited retained evidence containers may expose chip 1 historically. Any live
 # or created foreign reference blocks changing ownership.
 for item in q.docker('GET','/containers/json?all=1'):
  d=q.inspect(item['Id'])
  if d['State']['Status'] not in ('exited','dead'):
   require(not q.chip_access(d,1),'Active/created container still references chip 1')
 prep.free_now(q,1)


def recheck_actual(q,plan,bindings):
 for key,name in [('npu',plan['container']),('cpu',bindings['cpu_container_id'])]:
  actual=q.inspect(name)
  require(actual and actual['Id']==bindings[key+'_container_id']
    and actual['State']['Status']=='exited' and actual['State']['ExitCode']==0
    and actual['State']['StartedAt']==bindings[key+'_started_at']
    and actual['State']['FinishedAt']==bindings[key+'_finished_at'], 'Container exit changed during release')


def check_intent(intent,bindings,run,journal):
 require(intent['schema']=='e40-resource-release-intent-v1' and intent['bindings']==bindings
         and intent['run']==run and intent['chip']==1
         and intent['allocation_before_sha256']==bindings['approved_allocation_before_sha256'],
         'Pending release identity differs')
 before=intent['allocation_before'];after=intent['allocation_after']
 try:before_bytes=base64.b64decode(intent['allocation_before_bytes_b64'],validate=True)
 except Exception as exc:raise ValueError('Invalid original allocation bytes') from exc
 require(digest(before_bytes)==intent['allocation_before_sha256'] and json.loads(before_bytes)==before,
         'Intent original allocation bytes/hash/object differ')
 require(intent['allocation_before_bytes_b64']==bindings['approved_allocation_before_bytes_b64'],
         'Intent original allocation differs from independently pinned bytes')
 owners=[x for x in before['allocation'] if x['chip']==1]
 require(len(owners)==1 and owners[0]['run']==run and not any(x['chip']==1 for x in before['free']),
         'Intent before allocation has wrong owner')
 released=[x for x in after['free'] if x['chip']==1]
 require(len(released)==1 and set(released[0])=={'chip','previous_run','release_evidence','released_utc'}
         and released[0]['previous_run']==run and released[0]['release_evidence']==str(journal/'RELEASE_INTENT.json')
         and type(released[0]['released_utc']) is str and released[0]['released_utc'], 'Intent free entry differs')
 expected=copy.deepcopy(before);expected['allocation']=[x for x in expected['allocation'] if x['chip']!=1]
 expected['free'].append(released[0])
 require(after==expected and intent['allocation_after_sha256']==digest(encoded(after)),
         'Intent changes another resource or after hash differs')


def replace_allocation(q,value):
 """Publish the exact after bytes durably; allocation is the sole mutable file."""
 raw=encoded(value);tmp=ALLOCATION.with_name(ALLOCATION.name+'.e40-'+uuid.uuid4().hex+'.pending')
 fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
 try:
  with os.fdopen(fd,'wb') as stream:
   stream.write(raw);stream.flush();os.fsync(stream.fileno())
  q.verify()
  os.replace(tmp,ALLOCATION)
  directory=os.open(ALLOCATION.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:os.fsync(directory)
  finally:os.close(directory)
 finally:
  if tmp.exists():tmp.unlink()
 q.snapshots.pop(os.path.abspath(ALLOCATION),None)
 require(q.sha(ALLOCATION)==digest(raw),'Allocation publication bytes differ')


def intent_commit(q,journal,intent_path):
 path=journal/'INTENT_COMMITTED.json'
 expected=dict(intent_sha256=q.sha(intent_path))
 require(q.load(path)==expected,'Release intent changed after durable commitment')
 settle_publication(q,path,expected)
 return q.sha(path)


def settle_publication(q,path,value):
 pending=path.with_name(path.name+'.pending')
 if pending.exists() or pending.is_symlink():
  q.verify();evidence.publish_new(path,value)
  q.snapshots.pop(os.path.abspath(pending),None)
  q.snapshots.pop(os.path.abspath(path),None)
  require(q.load(path)==value,'Recovered publication differs')


def transaction(q,prep,plan,bindings,journal):
 require(journal.parent==ROOT and journal.name.startswith('e40_release_') and not journal.is_symlink(), 'Release journal location differs')
 journal.mkdir(exist_ok=True)
 with exclusive_lock(journal/'release.lock'):
  with exclusive_lock(Path(str(ALLOCATION)+'.lock')):
   intent_path=journal/'RELEASE_INTENT.json';done=journal/'RELEASED.json'
   run='reference_inference/'+Path(plan['out']).name
   if done.exists():
    intent=q.load(intent_path);terminal=q.load(done)
    check_intent(intent,bindings,run,journal)
    settle_publication(q,intent_path,intent)
    commitment=intent_commit(q,journal,intent_path)
    require(intent['bindings']==bindings and terminal==dict(rc=0,status='RELEASED',intent_sha256=q.sha(intent_path),intent_commit_sha256=commitment,
      allocation_before_sha256=intent['allocation_before_sha256'],allocation_after_sha256=intent['allocation_after_sha256']),
      'Completed release identity differs')
    settle_publication(q,done,terminal)
    q.verify();return dict(terminal,status='ALREADY_RELEASED')
   current=q.load(ALLOCATION);current_hash=q.sha(ALLOCATION);run='reference_inference/'+Path(plan['out']).name
   pending_intent=intent_path.with_name(intent_path.name+'.pending')
   if intent_path.exists() or pending_intent.exists() or pending_intent.is_symlink():
    intent=q.load(intent_path if intent_path.exists() else pending_intent)
    check_intent(intent,bindings,run,journal)
    settle_publication(q,intent_path,intent)
   else:
    require(current_hash == bindings['approved_allocation_before_sha256'],
            'Current allocation is not the parent-reviewed before state')
    owners=[x for x in current['allocation'] if x['chip']==1];free=[x for x in current['free'] if x['chip']==1]
    require(len(owners)==1 and owners[0]['run']==run and not free,'Release does not own exact chip-1 run')
    after=copy.deepcopy(current);after['allocation']=[x for x in after['allocation'] if x['chip']!=1]
    after['free'].append(dict(chip=1,previous_run=run,release_evidence=str(intent_path),released_utc=q.utc()))
    intent=dict(schema='e40-resource-release-intent-v1',chip=1,run=run,bindings=bindings,
      allocation_before_sha256=current_hash,allocation_after_sha256=digest(encoded(after)),
      allocation_before=current,allocation_before_bytes_b64=base64.b64encode(q.snapshot(ALLOCATION).data).decode(),allocation_after=after)
    check_intent(intent,bindings,run,journal)
    recheck_actual(q,plan,bindings);empty_now(q,prep);q.verify();evidence.publish_new(intent_path,intent)
   require(current_hash in (intent['allocation_before_sha256'],intent['allocation_after_sha256']),
           'Allocation changed outside exact pending release; preserve journal')
   commit_path=journal/'INTENT_COMMITTED.json'
   if not commit_path.exists():
    require(current_hash==intent['allocation_before_sha256'],'Mutation without committed intent; preserve journal')
    recheck_actual(q,plan,bindings);empty_now(q,prep);q.verify()
    evidence.publish_new(commit_path,dict(intent_sha256=q.sha(intent_path)))
   commitment=intent_commit(q,journal,intent_path)
   recheck_actual(q,plan,bindings);empty_now(q,prep);q.verify()
   if current_hash==intent['allocation_before_sha256']:
    require(current==intent['allocation_before'],'Before allocation differs')
    replace_allocation(q,intent['allocation_after'])
   require(q.sha(ALLOCATION)==intent['allocation_after_sha256'],'After allocation differs')
   terminal=dict(rc=0,status='RELEASED',intent_sha256=q.sha(intent_path),intent_commit_sha256=commitment,
     allocation_before_sha256=intent['allocation_before_sha256'],allocation_after_sha256=intent['allocation_after_sha256'])
   q.verify();evidence.publish_new(done,terminal)
   return terminal


def frozen_context(plan_path):
 require(plan_path.parent.name in PLAN_HASHES,'Unknown E40 plan')
 initial=evidence.Evidence();require(initial.sha(plan_path)==PLAN_HASHES[plan_path.parent.name],'Frozen E40 plan changed')
 plan=initial.load(plan_path);source_bytes={}
 for path,pin in plan['files'].items():
  if path.endswith('.py'):
   snap=initial.snapshot(path);require(snap.data is not None and snap.sha256==pin,'Frozen Python dependency changed')
   source_bytes[os.path.abspath(path)]=snap.data
 initial.verify()
 def frozen_module(path,name):
  key=os.path.abspath(path);require(key in source_bytes,'Unlisted dynamic dependency')
  value=importlib.util.module_from_spec(importlib.util.spec_from_loader(name,loader=None));value.__file__=key
  exec(compile(source_bytes[key],key,'exec'),value.__dict__);return value
 queue=frozen_module(plan_path.parent/'jeval_reference_queue.py','e40_release_queue')
 prep=frozen_module(plan_path.parent/'prepare_openjev_path_trace.py','e40_release_host')
 prep.frozen_module=frozen_module;prep.module=frozen_module
 q=evidence.Evidence(queue);prep.host(q)
 return q,prep


def release(plan_path,verification_request,review_path,journal,anchor_path,anchor_sha256):
 q,prep=frozen_context(plan_path)
 p,bindings=bind(plan_path,verification_request,review_path,q,prep,anchor_path,anchor_sha256)
 try:return transaction(q,prep,p,bindings,journal)
 except Exception as exc:
  if journal.parent==ROOT and journal.name.startswith('e40_release_') and journal.is_dir() and not journal.is_symlink():
   evidence.publish_new(journal/('FAILURE-'+str(time.time_ns())+'.json'),dict(rc=1,status='RELEASE_FAILED',
      error=type(exc).__name__+': '+str(exc),plan_sha256=bindings['plan_sha256'],
      recovery='Preserve intent/commitment; rerun only after exact pending before/after state checks'))
  raise


if __name__=='__main__':
 parser=argparse.ArgumentParser()
 for flag in ['plan','verification-request']:parser.add_argument('--'+flag,type=Path,required=True)
 for flag in ['review','journal','anchor']:parser.add_argument('--'+flag,type=Path)
 parser.add_argument('--anchor-sha256')
 args=parser.parse_args()
 require(all([args.review,args.journal,args.anchor,args.anchor_sha256]),'Release review, journal and pinned anchor required')
 result=release(args.plan,args.verification_request,args.review,args.journal,args.anchor,args.anchor_sha256)
 print(json.dumps(result))
