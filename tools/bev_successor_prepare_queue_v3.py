"""Prepare a dependency graph after durable physical releases; never launch NPU.

Exact execution review and launch are external. Only the predecessor release gates
preparation: predecessor CPU scoring and scientific result acceptance do not.
"""
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,threading,time,types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def put(p,d):
 p=Path(p);tmp=p.with_name(p.name+'.pending')
 with tmp.open('w') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def ref(p):return dict(path=str(p),sha256=sha(p))
def module(r):
 require(sha(r['path'])==r['sha256'],'module changed');m=types.ModuleType('binding');m.__file__=r['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m
def inspect(name):
 result=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
 require(result.returncode==0,'container observation uncertain');return json.loads(result.stdout)[0]
def released(job,allocation,query=inspect):
 """Return proof only for exact successful predecessor and current free generation."""
 root=Path(job['predecessor_root']);p=root/'PLAN.json';h=root/'output/host_attempts/1'
 if not (h/'RELEASE.json').exists():return None
 d=read(p);release=read(h/'RELEASE.json');claim=read(h/'CLAIM.json');terminal=read(h/'EXIT.json');runtime=read(root/'output/attempts/1/EXIT.json');receipt=read(h/'LAUNCH_RECEIPT.json')
 pin=sha(p);chip=job['chip'];expected='r3_runs/'+root.name
 require(d['run']==expected and d['chip']==chip,'predecessor plan differs')
 if job.get('predecessor_plan_sha256'):require(pin==job['predecessor_plan_sha256'],'predecessor plan changed')
 for obj in (release,claim):require(obj['run']==expected and type(obj['chip'])is int and obj['chip']==chip,'predecessor identity')
 require(release['schema']=='r3-resource-release-v1' and claim['schema']=='r3-resource-claim-v1' and release['claim_sha256']==sha(h/'CLAIM.json'),'release binding')
 for obj in (release,terminal,runtime):require(type(obj.get('exit_code'))is int and obj['exit_code']==0 and obj.get('scientific_acceptance')is False,'predecessor unsuccessful')
 require(terminal.get('runner_terminal_matches')is True,'runtime terminal unmatched')
 for obj in (terminal,runtime,receipt):require(obj.get('plan_sha256')==pin and type(obj.get('attempt'))is int and obj['attempt']==1,'terminal plan/attempt')
 require(receipt['container_id']==terminal['container_id']==release['container_id'],'container lineage')
 require(release['container']==d['container']+'-a1','container name')
 free=[x for x in allocation['free'] if x['chip']==chip]
 if any(x['chip']==chip for x in allocation['allocation']) or len(free)!=1:return None
 require(free[0]['previous_run']==expected and free[0]['release_evidence']==str(h/'RELEASE.json'),'different free predecessor')
 require([x for x in release['allocation_after']['free'] if x['chip']==chip]==free,'free generation')
 actual=query(release['container']);state=actual['State']
 require(actual['Id']==release['container_id'] and state.get('Running')is False and state.get('Status')=='exited','physical release missing')
 require(type(state['ExitCode'])is int and state['ExitCode']==0 and state['StartedAt']==release['container_started_at'] and state['FinishedAt']==release['container_finished_at'],'physical generation differs')
 require(actual['HostConfig'].get('AutoRemove')is False and actual.get('RestartCount')==0,'retained lifecycle')
 require(any(x['PathOnHost']=='/dev/davinci'+str(chip) for x in actual['HostConfig']['Devices']),'device binding')
 return dict(predecessor_plan=ref(p),release=ref(h/'RELEASE.json'),claim=ref(h/'CLAIM.json'),container_id=actual['Id'],free_entry=free[0])
def validate(c):
 require(c['schema']=='bev-successor-prepare-queue-v3' and c['poll_seconds']==600 and c['workers'] in (1,2),'queue bounds')
 require(c['npu_launch_allowed']is False and c['scientific_acceptance']is False,'queue scope')
 require(len({j['id'] for j in c['jobs']})==len(c['jobs']),'duplicate node')
 require(len({j['output_root'] for j in c['jobs']})==len(c['jobs']),'output collision')
 for p,h in c['files'].items():require(sha(p)==h,'configuration dependency changed: '+p)
 for j in c['jobs']:
  require(j['base_config'] in c['files'] and j['decision'] in c['files'],'unbound inputs')
  require(j['predecessor_root']!=j['output_root'],'self dependency')
 return c
class BuilderReconciliationRequired(BaseException):
 pass

def stop_owned_builder(proc, identity):
 # This Popen is still an unreaped direct child: the kernel cannot reuse its
 # PID. Do not poll/wait before signalling its session, including on exceptions.
 require(proc.returncode is None,'builder already reaped before cleanup')
 pid=proc.pid
 if identity is not None:
  actual=process_identity(pid)
  require(actual['boot_id']==identity['boot_id'] and actual['start_ticks']==identity['start_ticks'],'builder identity changed')
 require(os.getpgid(pid)==pid and os.getsid(pid)==pid,'builder session differs')
 fd=os.pidfd_open(pid)
 try:
  try:os.killpg(pid,signal.SIGTERM)
  except ProcessLookupError:pass
  # Hold the unreaped leader/Popen until after the group escalation. Descendants
  # ignoring SIGTERM must not survive a failed SERVICE publication.
  time.sleep(2)
  try:os.killpg(pid,signal.SIGKILL)
  except ProcessLookupError:pass
  return proc.wait()
 finally:os.close(fd)

def execute_builder(cmd,environment,node):
 # Ownership lives in the stack before identity capture or any disk write.
 # Exceptions cannot skip the owned child's wait as they did in v1/v2.
 with (node/'builder.log').open('ab') as log:
  proc=subprocess.Popen(cmd,env=dict(os.environ,**environment),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  identity=None
  try:
   identity=process_identity(proc.pid)
   put(node/'SERVICE.json',dict(pid=proc.pid,command=cmd,process=identity))
   return proc.wait()
  except BaseException:
   # Never convert an unobserved child into a success terminal. If an identity
   # check itself fails, the failure propagates and requires reconciliation.
   if proc.returncode is None:
    try:rc=stop_owned_builder(proc,identity)
    except BaseException as cleanup_error:raise BuilderReconciliationRequired('owned builder cleanup uncertain; reconcile PID '+str(proc.pid)) from cleanup_error
    put(node/'CHILD-STOP.json',dict(process=identity,pid=proc.pid,exit_code=rc,reason='post_spawn_failure',npu_launched=False))
    put(node/'EXIT.json',dict(exit_code=1,child_exit_code=rc,utc_seconds=time.time(),npu_launched=False,reason='post_spawn_failure'))
   raise

def prepare(c,job,proof):
 root=Path(c['output']);node=root/job['id'];node.mkdir(exist_ok=False);put(node/'RELEASE-OBSERVATION.json',proof)
 B=module(c['binder']);config=node/'PREPARE.json';B.bind(job['base_config'],c['allocation'],job['chip'],job['output_root'],str(config),job['decision'])
 cmd=[c['python'],'-B','-P',c['builder']['path'],'--config',str(config)]
 put(node/'RELAUNCH.json',dict(command=cmd,environment=c['environment'],automatic_retry=False))
 rc=execute_builder(cmd,c['environment'],node)
 put(node/'EXIT.json',dict(exit_code=rc,utc_seconds=time.time(),npu_launched=False))
 require(rc==0,'builder failed; new generation required')
 output=Path(job['output_root']);result=read(output/'PREPARATION.json')
 require(result['npu_launched']is False and result['status']=='PREPARED_NOT_ACTIVATED','preparation scope')
 request=dict(schema='successor-exact-review-request-v1',job=job['id'],plan=ref(output/'PLAN.json'),config=ref(output/'CONFIG.json'),predecessor=proof,activation_authorized=False,scientific_acceptance=False,npu_launched=False,required=['independent exact execution review','current free-generation physical checks at claim','parent launch'])
 put(node/'REVIEW-REQUEST.json',request);return request
def once(c):
 root=Path(c['output']);state=[];eligible=[]
 for j in c['jobs']:
  node=root/j['id']
  if (node/'REVIEW-REQUEST.json').exists():state.append(dict(id=j['id'],state='prepared_pending_review',review_request=str(node/'REVIEW-REQUEST.json')));continue
  if node.exists():state.append(dict(id=j['id'],state='interrupted_or_failed_needs_reconciliation'));continue
  try:
   proof=released(j,read(c['allocation']))
   if proof is None:state.append(dict(id=j['id'],state='waiting_exact_release'));continue
   eligible.append((j,proof))
  except Exception as e:state.append(dict(id=j['id'],state='blocked_observation',error=str(e)[:250]))
 with ThreadPoolExecutor(max_workers=c['workers']) as pool:
  futures=[(j,pool.submit(prepare,c,j,proof)) for j,proof in eligible]
  for j,f in futures:
   try:f.result();state.append(dict(id=j['id'],state='prepared_pending_review'))
   except Exception as e:state.append(dict(id=j['id'],state='preparation_failed',error=str(e)[:250]))
 put(root/'digest.json',dict(utc_seconds=time.time(),jobs=state,npu_launched=False));(root/'digest.md').write_text('# Successor preparation queue\n\n'+ '\n'.join('- '+r['id']+': '+r['state'] for r in state)+'\n')
 return state
def process_identity(pid):
 p=Path('/proc')/str(pid);fields=p.joinpath('stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(fields[19]),argv=p.joinpath('cmdline').read_bytes().decode().rstrip('\0').split('\0'))

def run(config,pin,one_pass=False):
 require(sha(config)==pin,'config changed');c=validate(read(config));root=Path(c['output']);root.mkdir(exist_ok=True)
 with (root/'queue.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  # SIGUSR1 requests a new pass. During a pass it remains set, so a release
  # cannot get lost between validation and the subsequent wait.
  wake=threading.Event();stop=threading.Event();heartbeat_stop=threading.Event();old={};stop_signal=[]
  def request_stop(signum,frame):stop_signal.append(signum);stop.set();wake.set()
  for sig,handler in [(signal.SIGUSR1,lambda *_:wake.set()),(signal.SIGTERM,request_stop),(signal.SIGINT,request_stop)]:
   old[sig]=signal.signal(sig,handler)
  put(root/'SERVICE.json',dict(process=process_identity(os.getpid()),config_sha256=pin,signals=dict(wake='SIGUSR1',stop='SIGTERM/SIGINT'),npu_launched=False))
  put(root/'RELAUNCH.json',dict(command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--config',str(Path(config).resolve()),'--sha256',pin],automatic_restart=False,recovery='Existing node without REVIEW-REQUEST is never retried automatically; reconcile its real builder before a new generation.'))
  def beat():
   while not heartbeat_stop.wait(30):put(root/'heartbeat.json',dict(utc_seconds=time.time(),state='stopping_after_builders' if stop.is_set() else 'alive',npu_launched=False))
  t=threading.Thread(target=beat,daemon=True);t.start();rc=1;reason='error';reconciled=True
  try:
   while not stop.is_set():
    wake.clear()
    require(sha(config)==pin,'config changed while running');validate(c);state=once(c)
    if all(x['state']=='prepared_pending_review' for x in state):rc=0;reason='prepared';break
    if one_pass:
     rc=1 if any(x['state'] in ('preparation_failed','interrupted_or_failed_needs_reconciliation','blocked_observation') for x in state) else 0
     reason='one_pass_failed' if rc else 'one_pass_observed';break
    if stop.is_set():break
    wake.wait(c['poll_seconds'])
   if stop.is_set():rc=128+stop_signal[0];reason='operator_stop_after_builders'
  except BuilderReconciliationRequired:
   reconciled=False;reason='owned_builder_requires_reconciliation';raise
  finally:
   # once() owns and waits for every detached builder future. Orderly stop
   # never abandons a builder or fabricates an experiment terminal.
   heartbeat_stop.set();t.join(2)
   put(root/'QUEUE-EXIT.json',dict(exit_code=rc,reason=reason,utc_seconds=time.time(),npu_launched=False,scope='prepare_controller_not_experiment',builders_reconciled=reconciled))
   for sig,handler in old.items():signal.signal(sig,handler)
 return rc

def main():
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);a.add_argument('--once',action='store_true');args=a.parse_args()
 sys.exit(run(args.config,args.sha256,args.once))
if __name__=='__main__':main()
