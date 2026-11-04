"""Detached CPU recovered-training collection/review/DEV-preparation service.

Fixed SSH read-only Docker queries; no training/evaluation launch or device claim.
"""
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,threading,time,types
from pathlib import Path

def need(v,s):
 if not v:raise ValueError(s)
def safe(v):
 p=Path(v);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p
def sha(p):
 with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def pinned(r):need(set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'pin changed');return safe(r['path'])
def module(r):
 p=pinned(r);m=types.ModuleType(p.stem);m.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
def put(p,d,exclusive=False):
 import tempfile
 p=safe(p);p.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=p.name+'.',suffix='.pending',dir=p.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
  if exclusive:os.link(tmp,p)
  else:os.replace(tmp,p)
  fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 finally:Path(tmp).unlink(missing_ok=True)
def process(pid):
 r=Path('/proc')/str(pid);return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int((r/'stat').read_text().rsplit(')',1)[1].split()[19]),'command':(r/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')}
def identity(path,pin):
 need(sha(path)==pin,'config changed');c=read(path)
 need(c['schema']=='r3-training-resume-service-v1' and c['scientific_acceptance'] is False and c['test_read'] is False and c['evaluation_authorized'] is False,'service scope')
 need(pinned(c['controller'])==Path(__file__).resolve(),'service controller')
 need(type(c['poll_interval_seconds']) is int and c['poll_interval_seconds']>=600,'cadence')
 need(c['ssh_host']=='npu','fixed SSH host required')
 C=module(c['collector_controller']);cc=read(pinned(c['collector']));need(cc['controller']==c['collector_controller'],'collector differs')
 _,H,b,p,j,base,binder,L,O=C.identity(c['collector']['path'],c['collector']['sha256'])
 root=safe(c['state_root']);observe=safe(c['observation_root']);review=safe(c['review_reference'])
 H.disjoint(root,observe,Path(p['out']),Path(b['state_root']),Path(b['evaluation_out']),Path(cc['output']).parent)
 need(not review.is_relative_to(root) and not review.is_relative_to(Path(p['out'])) and not review.is_relative_to(Path(b['state_root'])),'review reference inside producer')
 return c,C,cc,H,b,p,root

def authorize(c,pin,activation):
 a=read(pinned(activation));need(a['schema']=='r3-recovery-cpu-service-activation-v1' and a['config_sha256']==pin and a['start_authorized'] is True and a['scientific_acceptance'] is False and a['test_read'] is False,'activation scope')
 r=read(pinned(a['review']));need(r['verdict']=='PASS' and r['config_sha256']==pin and r['cpu_service_activation_authorized'] is True and r['scientific_acceptance'] is False,'exact independent service review required')
 return a

def observe(c,p,capture_sha,run=subprocess.run):
 root=safe(c['observation_root']);root.mkdir(parents=True,exist_ok=True)
 # Attempt directories are append-only; transport failures cannot be adopted as observations.
 index=1
 while (root/f'attempt-{index}').exists():index+=1
 out=root/f'attempt-{index}';out.mkdir()
 commands={'container':['docker','inspect',p['container']+'-a1'],'image':['docker','image','inspect',p['image_sha256']],'daemon':['docker','info','--format','{{json .}}']}
 import shlex
 pins={};started=time.time()
 try:
  for name,argv in commands.items():
   put(out/(name+'-INTENT.json'),{'host':'npu','argv':argv,'utc_seconds':time.time()},True)
   x=run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','npu',shlex.join(argv)],capture_output=True,text=True,timeout=45)
   if x.returncode:raise OSError('Docker observation transport/command failed: '+name)
   try:d=json.loads(x.stdout)
   except json.JSONDecodeError as error:raise OSError('Docker observation JSON unavailable: '+name) from error
   target=out/(name+'.json');put(target,d,True);pins[name]={'path':str(target),'sha256':sha(target)}
  manifest={'schema':'r3-postrun-external-observations-v1','training':p['out'],'capture_sha256':capture_sha,'observations':pins,'observed_start_utc_seconds':started,'observed_end_utc_seconds':time.time(),'origin':'local CPU service invoking fixed ssh npu Docker queries; independent origin authentication still required'}
  target=out/'OBSERVATIONS.json';put(target,manifest,True);put(out/'EXIT.json',{'exit_code':0,'utc_seconds':time.time()},True);return {'path':str(target),'sha256':sha(target)}
 except BaseException:
  put(out/'EXIT.json',{'exit_code':1,'utc_seconds':time.time(),'observation_accepted':False},True);raise

def tick(path,pin):
 c,C,cc,H,b,p,root=identity(path,pin);cap=H.inspect(cc['handoff']['path'],cc['handoff']['sha256'],persist=True)
 if cap['status']!='REVIEW_REQUIRED':return {'status':cap['status']}
 report=Path(cc['output']);cp=Path(b['state_root'])/'CAPTURE.json';ptr=root/'OBSERVATIONS-REFERENCE.json'
 if not report.exists():
  if ptr.exists():oref=read(ptr);pinned(oref)
  else:
   try:oref=observe(c,p,sha(cp))
   except (OSError,subprocess.TimeoutExpired):return {'status':'observation_unknown','action':'retry_observation_only_after_interval'}
   put(ptr,oref,True)
  C.collect(c['collector']['path'],c['collector']['sha256'],oref['path'],oref['sha256'])
  put(root/'COLLECTION-REFERENCE.json',{'path':str(report),'sha256':sha(report)},True)
 else:
  need((root/'COLLECTION-REFERENCE.json').exists(),'unowned collection; no adoption');pinned(read(root/'COLLECTION-REFERENCE.json'))
 rp=Path(c['review_reference'])
 if not rp.exists():return {'status':'waiting_independent_postrun_review','collection':str(report)}
 rr=read(rp);need(rr.get('config_sha256')==pin and set(rr)=={'config_sha256','review'},'review reference differs');pinned(rr['review'])
 # Exact pinned independent review must include collected physical evidence.
 review=read(rr['review']['path']);need(review.get('evidence_files',{}).get(str(report))==sha(report),'review omits actual collection')
 target=Path(b['state_root'])/'PREPARED.json'
 if target.exists():
  own=root/'PREPARED-REFERENCE.json';need(own.exists(),'unowned prepared result');pinned(read(own));return {'status':'prepared','evaluation_authorized':False}
 result=H.prepare(cc['handoff']['path'],cc['handoff']['sha256'],rr['review']);put(root/'PREPARED-REFERENCE.json',{'path':str(target),'sha256':sha(target)},True)
 return {'status':'prepared','evaluation_authorized':False}

def watch(path,pin,activation):
 need(sha(path)==pin,'config changed');c=read(path);root=safe(c['state_root']);root.mkdir(parents=True,exist_ok=True)
 lock=(root/'watch.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BaseException:lock.close();raise # Duplicate watch must not alter original terminal.
 if (root/'EXIT.json').exists():lock.close();raise ValueError('service already terminal')
 stop=threading.Event();rc=1;status='failed'
 def stop_signal(*unused):stop.set()
 if threading.current_thread() is threading.main_thread():signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
 def heartbeat():
  while not stop.wait(30):put(root/'heartbeat.json',{'status':'cpu_service_alive','utc_seconds':time.time()})
 worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
 try:
  with lock:
   c,C,cc,H,b,p,root=identity(path,pin);authorize(c,pin,activation)
   intent=read(root/'START-INTENT.json');need(intent['config_sha256']==pin and intent['activation']==activation,'start intent differs')
   while not stop.is_set():
    authorize(c,pin,activation);r=tick(path,pin);put(root/'digest.json',dict(r,utc_seconds=time.time(),scientific_acceptance=False,test_read=False))
    if r['status']=='prepared':rc=0;status='prepared';break
    if r['status']=='training_failed':status='training_failed';break
    stop.wait(c['poll_interval_seconds'])
   else:rc=0;status='stopped'
 except BaseException as error:
  put(root/'ERROR.json',{'error_type':type(error).__name__,'error':str(error)[:500],'automatic_retry':False});raise
 finally:
  stop.set();worker.join(2);put(root/'EXIT.json',{'exit_code':rc,'status':status,'utc_seconds':time.time(),'evaluation_authorized':False,'scientific_acceptance':False})

def start(path,pin,activation):
 c,*rest=identity(path,pin);root=rest[-1];authorize(c,pin,activation);root.mkdir(parents=True,exist_ok=True)
 with (root/'start.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  need(not (root/'EXIT.json').exists() and not (root/'SERVICE.json').exists(),'previous service exists')
  cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'watch','--config',str(path),'--sha256',pin,'--activation',activation['path'],'--activation-sha256',activation['sha256']]
  put(root/'START-INTENT.json',{'config_sha256':pin,'activation':activation,'command':cmd,'utc_seconds':time.time()},True)
  put(root/'RELAUNCH.json',{'command':cmd,'automatic_retry':False,'instruction':'Inspect exact PID/generation and terminal. Existing intent is not permission to retry.'},True)
  try:
   with (root/'service.log').open('ab') as log:child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
   state=process(child.pid);need(state['command']==cmd,'spawn identity differs');put(root/'SERVICE.json',state,True)
  except BaseException as error:put(root/'START-ERROR.json',{'error_type':type(error).__name__,'automatic_retry':False});raise
 return {'status':'started','pid':child.pid}

def main():
 a=argparse.ArgumentParser();a.add_argument('op',choices=['verify','start','watch']);a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);a.add_argument('--activation');a.add_argument('--activation-sha256');v=a.parse_args()
 if v.op=='verify':identity(v.config,v.sha256);result={'status':'verified','start_authorized':False}
 else:
  need(v.activation and v.activation_sha256,'external activation required');activation={'path':v.activation,'sha256':v.activation_sha256}
  if v.op=='start':result=start(v.config,v.sha256,activation)
  elif v.op=='watch':watch(v.config,v.sha256,activation);return
 print(json.dumps(result))
if __name__=='__main__':main()
