#!/usr/bin/env python3
"""Independent E38 chip-4 release transaction; never launches a container."""
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
PLAN_HASHES = {
 'openjev_path_trace_openjev2_20261031_v4': '882b686ba62c75f1bb41c670b18fb4785f439273bbd32b4c5de29ff9a512a8df',
 'openjev_path_trace_openjev9_20261031_v4': 'b1afb0e81a5c3c77f6bb5892e8dfdb7da750220d6d44f17dc2a7e52b6d9afce3',
}


def module(path, name):
 spec=importlib.util.spec_from_file_location(name,path)
 value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


evidence=module(Path(__file__).with_name('e38_evidence.py'),'e38_release_evidence')
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


def bind(plan_path, verification_request, review_path, q, prep):
 p=q.load(plan_path);ph=q.sha(plan_path);out=plan_path.parent
 require(out.parent==ROOT and out.name in PLAN_HASHES and ph==PLAN_HASHES[out.name], 'Unreviewed release target plan')
 require(p['out']==str(out) and p['physical_chip']==4 and p['allocation']==str(ALLOCATION)
         and p['execution_revision']=='astra-v3-strict-attempts' and p['candidate_batch_admission'] is False,
         'E38 chip-4 release identity differs')
 require(q.load(out/'PARENT_REVIEW.json')['approved_plan_sha256']==ph,'Parent launch review differs')
 astra=q.load(out/'INDEPENDENT_REVIEW.json')
 require(astra['approved'] is True and astra['approved_plan_sha256']==ph
         and q.sha(astra['review_path'])==astra['review_sha256'],'Actual independent launch review differs')
 prep.preparation_binding(q,plan_path,p)
 require(verification_request.parent.parent==ROOT,'CPU verifier request location differs')
 r,cpu=prep.cpu_binding(q,verification_request,'exited')
 require(r['task']=='verify' and r['target_plan']==str(plan_path) and cpu['State']['ExitCode']==0
         and not q.devices(cpu),'CPU result verification identity/exit differs')
 vout=verification_request.parent;vr=q.load(vout/'report.json');vt=q.load(vout/'COMPLETE.json')
 require(vt['rc']==0 and vt['stage']=='completed' and vt['progress']==vt['total']==1
         and vt['request_sha256']==q.sha(verification_request)
         and vt['outputs']=={'report.json':q.sha(vout/'report.json')}
         and re.fullmatch(r'rc=0 utc=\S+\n?',q.snapshot(vout/'EXIT').data.decode()),'CPU verifier terminal/EXIT differs')
 require(vr['plan_sha256']==ph and vr['actual_exit']==0 and vr['candidate_batch_admission'] is False,
         'CPU verifier result differs')
 d=q.inspect(p['container']);launch=q.load(out/'LAUNCH_RECEIPT.json')
 q.binding(d,q.load(p['container_spec']),launch)
 require(d['State']['Status']=='exited' and d['State']['ExitCode']==0
         and d['Id']==vr['container_id'] and launch['plan_sha256']==ph
        and d['State']['StartedAt']==vr['npu_started_at']
        and d['State']['FinishedAt']==vr['npu_finished_at']
         and launch['wrapper_sha256']==q.sha(p['wrapper']), 'Actual NPU exit/identity differs')
 require(not any((out/n).exists() for n in ['FAILED_GENERATION.json','FAILURE.json']), 'Failed NPU generation cannot use normal release')
 terminal=q.load(out/'COMPLETE.json');report=q.load(out/'report.json')
 require(q.sha(out/'COMPLETE.json')==vr['terminal_sha256'] and q.sha(out/'report.json')==vr['report_sha256']
         and terminal['rc']==0 and terminal['plan_sha256']==ph and terminal['stage']=='completed'
         and terminal['progress']==terminal['total']==8 and terminal['trace_valid'] is vr['trace_valid']
         and re.fullmatch(r'rc=0 utc=\S+\n?',q.snapshot(out/'EXIT').data.decode()),'Verified NPU terminal/report changed')
 for name,h in terminal['outputs'].items():require(q.sha(out/name)==h,'NPU terminal output changed')
 for folder,key in [('items','receipt_manifest'),('attempts','attempt_manifest')]:
  manifest=vr[key]
  require(len(manifest)==8 and report[key]==manifest
          and sorted(x.name for x in (out/folder).iterdir())==sorted(manifest),'Verified receipt/attempt population changed')
  for name,h in manifest.items():require(q.sha(out/folder/name)==h,'Verified receipt/attempt changed')
 review=q.load(review_path)
 require(review['schema']=='e38-resource-release-review-v1' and review['approved'] is True
         and review['approved_plan_sha256']==ph
         and review['verification_request_sha256']==q.sha(verification_request)
         and review['verification_report_sha256']==q.sha(vout/'report.json')
         and review['verification_terminal_sha256']==q.sha(vout/'COMPLETE.json')
         and review['accepted_trace_valid'] is vr['trace_valid']
         and review['accepted_review_flags']==terminal['review_flags']
         and review['candidate_batch_admission'] is False
         and review['release_tool_sha256']==q.sha(Path(__file__))
         and review['evidence_helper_sha256']==q.sha(Path(__file__).with_name('e38_evidence.py')),
         'Parent release review differs or omits scientific flags/tool identity')
 return p,dict(plan_sha256=ph,verification_request_sha256=q.sha(verification_request),
  verification_report_sha256=q.sha(vout/'report.json'),verification_terminal_sha256=q.sha(vout/'COMPLETE.json'),
  verification_exit_sha256=q.sha(vout/'EXIT'),release_review_sha256=q.sha(review_path),
  release_tool_sha256=review['release_tool_sha256'],evidence_helper_sha256=review['evidence_helper_sha256'],
  npu_container_id=d['Id'],npu_finished_at=d['State']['FinishedAt'],cpu_container_id=cpu['Id'],
  cpu_finished_at=cpu['State']['FinishedAt'],npu_terminal_sha256=vr['terminal_sha256'],
  npu_report_sha256=vr['report_sha256'],npu_exit_sha256=q.sha(out/'EXIT'),
  accepted_trace_valid=vr['trace_valid'],accepted_review_flags=terminal['review_flags'],candidate_batch_admission=False)


def empty_now(q,prep):
 # Exited retained evidence containers may expose chip 4 historically. Any live
 # or created foreign reference blocks changing ownership.
 for item in q.docker('GET','/containers/json?all=1'):
  d=q.inspect(item['Id'])
  if d['State']['Status'] not in ('exited','dead'):
   require(not q.chip_access(d,4),'Active/created container still references chip 4')
 prep.free_now(q,4)


def recheck_actual(q,plan,bindings):
 for key,name in [('npu',plan['container']),('cpu',bindings['cpu_container_id'])]:
  actual=q.inspect(name)
  require(actual and actual['Id']==bindings[key+'_container_id']
    and actual['State']['Status']=='exited' and actual['State']['ExitCode']==0
    and actual['State']['FinishedAt']==bindings[key+'_finished_at'], 'Container exit changed during release')


def check_intent(intent,bindings,run,journal):
 require(intent['schema']=='e38-resource-release-intent-v1' and intent['bindings']==bindings
         and intent['run']==run and intent['chip']==4, 'Pending release identity differs')
 before=intent['allocation_before'];after=intent['allocation_after']
 try:before_bytes=base64.b64decode(intent['allocation_before_bytes_b64'],validate=True)
 except Exception as exc:raise ValueError('Invalid original allocation bytes') from exc
 require(digest(before_bytes)==intent['allocation_before_sha256'] and json.loads(before_bytes)==before,
         'Intent original allocation bytes/hash/object differ')
 owners=[x for x in before['allocation'] if x['chip']==4]
 require(len(owners)==1 and owners[0]['run']==run and not any(x['chip']==4 for x in before['free']),
         'Intent before allocation has wrong owner')
 released=[x for x in after['free'] if x['chip']==4]
 require(len(released)==1 and set(released[0])=={'chip','previous_run','release_evidence','released_utc'}
         and released[0]['previous_run']==run and released[0]['release_evidence']==str(journal/'RELEASE_INTENT.json')
         and type(released[0]['released_utc']) is str and released[0]['released_utc'], 'Intent free entry differs')
 expected=copy.deepcopy(before);expected['allocation']=[x for x in expected['allocation'] if x['chip']!=4]
 expected['free'].append(released[0])
 require(after==expected and intent['allocation_after_sha256']==digest(encoded(after)),
         'Intent changes another resource or after hash differs')


def replace_allocation(q,value):
 """Publish the exact after bytes durably; allocation is the sole mutable file."""
 raw=encoded(value);tmp=ALLOCATION.with_name(ALLOCATION.name+'.e38-'+uuid.uuid4().hex+'.pending')
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
 return q.sha(path)


def transaction(q,prep,plan,bindings,journal):
 require(journal.parent==ROOT and journal.name.startswith('e38_release_') and not journal.is_symlink(), 'Release journal location differs')
 journal.mkdir(exist_ok=True)
 with exclusive_lock(journal/'release.lock'):
  with exclusive_lock(Path(str(ALLOCATION)+'.lock')):
   intent_path=journal/'RELEASE_INTENT.json';done=journal/'RELEASED.json'
   run='reference_inference/'+Path(plan['out']).name
   if done.exists():
    intent=q.load(intent_path);terminal=q.load(done)
    check_intent(intent,bindings,run,journal)
    commitment=intent_commit(q,journal,intent_path)
    require(intent['bindings']==bindings and terminal==dict(rc=0,status='RELEASED',intent_sha256=q.sha(intent_path),intent_commit_sha256=commitment,
      allocation_before_sha256=intent['allocation_before_sha256'],allocation_after_sha256=intent['allocation_after_sha256']),
      'Completed release identity differs')
    q.verify();return dict(terminal,status='ALREADY_RELEASED')
   current=q.load(ALLOCATION);current_hash=q.sha(ALLOCATION);run='reference_inference/'+Path(plan['out']).name
   if intent_path.exists():
    intent=q.load(intent_path)
    check_intent(intent,bindings,run,journal)
   else:
    owners=[x for x in current['allocation'] if x['chip']==4];free=[x for x in current['free'] if x['chip']==4]
    require(len(owners)==1 and owners[0]['run']==run and not free,'Release does not own exact chip-4 run')
    after=copy.deepcopy(current);after['allocation']=[x for x in after['allocation'] if x['chip']!=4]
    after['free'].append(dict(chip=4,previous_run=run,release_evidence=str(intent_path),released_utc=q.utc()))
    intent=dict(schema='e38-resource-release-intent-v1',chip=4,run=run,bindings=bindings,
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


def release(plan_path,verification_request,review_path,journal):
 # Import only from the previously reviewed frozen v4 executable closure.
 require(plan_path.parent.name in PLAN_HASHES,'Unknown E38 plan')
 initial=evidence.Evidence();require(initial.sha(plan_path)==PLAN_HASHES[plan_path.parent.name],'Frozen plan changed')
 plan=initial.load(plan_path)
 for name in ['prepare_openjev_path_trace.py','e38_evidence.py','jeval_reference_queue.py']:
  path=plan_path.parent/name;require(initial.sha(path)==plan['files'][str(path)],'Frozen release dependency changed')
 # Snapshot every Python dependency before executing any of it.  The frozen
 # preparer uses path-based imports; replace that loader with an in-memory
 # compiler so a later path replacement cannot change the code being run.
 source_bytes={}
 for path in plan['files']:
  if path.endswith('.py'):
   snap=initial.snapshot(path); require(snap.data is not None,'Python dependency exceeds bounded snapshot')
   source_bytes[os.path.abspath(path)]=snap.data
 initial.verify()
 def frozen_module(path,name):
  key=os.path.abspath(path); require(key in source_bytes,'Unlisted dynamic dependency: '+key)
  value=importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
  value.__file__=key; exec(compile(source_bytes[key],key,'exec'),value.__dict__)
  return value
 prep=frozen_module(plan_path.parent/'prepare_openjev_path_trace.py','e38_release_frozen_preparer')
 prep.module=frozen_module
 q=evidence.Evidence(prep.helper(plan_path.parent).delegate);prep.host(q)
 p,bindings=bind(plan_path,verification_request,review_path,q,prep)
 try:return transaction(q,prep,p,bindings,journal)
 except Exception as exc:
  if journal.parent==ROOT and journal.name.startswith('e38_release_') and journal.is_dir() and not journal.is_symlink():
   evidence.publish_new(journal/('FAILURE-'+str(time.time_ns())+'.json'),dict(rc=1,status='RELEASE_FAILED',
      error=type(exc).__name__+': '+str(exc),plan_sha256=bindings['plan_sha256'],
      recovery='Preserve intent/commitment; rerun only after exact pending before/after state checks'))
  raise


if __name__=='__main__':
 parser=argparse.ArgumentParser()
 for flag in ['plan','verification-request','review','journal']:parser.add_argument('--'+flag,type=Path,required=True)
 args=parser.parse_args()
 print(json.dumps(release(args.plan,args.verification_request,args.review,args.journal)))
