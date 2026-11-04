"""Post-release CPU operand reconstruction and matched-cost accounting."""
import argparse,fcntl,hashlib,json,os,subprocess,threading,time,types
from pathlib import Path

def need(v,s):
 if not v:raise ValueError(s)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def module(ref):
 raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'source changed');m=types.ModuleType('consumer');m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def put(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
 with tmp.open('w') as f:json.dump(d,f,allow_nan=False,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def lifecycle(d,pin):
 from datetime import datetime
 h=Path(d['out'])/'host_attempts/1';runtime=read(Path(d['out'])/'attempts/1/EXIT.json');end=read(h/'EXIT.json');release=read(h/'RELEASE.json');claim=read(h/'CLAIM.json');receipt=read(h/'LAUNCH_RECEIPT.json')
 need(runtime['exit_code']==end['exit_code']==release['exit_code']==0 and runtime['plan_sha256']==end['plan_sha256']==receipt['plan_sha256']==pin,'completion identity')
 need(end['runner_terminal_matches']is True and end['container_id']==release['container_id']==receipt['container_id'] and release['claim_sha256']==sha(h/'CLAIM.json'),'release identity')
 need(release['chip']==claim['chip']==d['chip'] and release['run']==claim['run']==d['run'],'resource identity')
 before=datetime.fromisoformat(claim['claimed_utc'].replace('Z','+00:00')).timestamp() if 'claimed_utc' in claim else None
 after=datetime.fromisoformat(release['released_utc'].replace('Z','+00:00')).timestamp()
 if before is None:
  entry=[x for x in claim['allocation_after']['allocation'] if x['run']==d['run'] and x['chip']==d['chip']];need(len(entry)==1,'claim time');before=datetime.fromisoformat(entry[0]['claimed_utc'].replace('Z','+00:00')).timestamp()
 need(after>=before,'negative resource occupation');return {'resource_occupied_seconds':after-before,'resource_occupied_chip_hours':(after-before)/3600,'chips':1,'claim_sha256':sha(h/'CLAIM.json'),'release_sha256':sha(h/'RELEASE.json')}
def start(d,path,pin,attempt):
 need(attempt==1,'attempt');lifecycle(d,pin);root=Path(d['out'])/'cpu';root.mkdir(exist_ok=True)
 intent=root/'START-INTENT.json';cmd=[d['cpu_python'],'-B','-P',str(Path(__file__).resolve()),'consume','--plan',str(path),'--sha256',pin]
 with intent.open('x') as f:json.dump({'command':cmd,'plan_sha256':pin,'automatic_retry':False},f);f.flush();os.fsync(f.fileno())
 with (root/'consumer.log').open('ab') as log:p=subprocess.Popen(cmd,env=dict(os.environ,**d['cpu_environment']),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 put(root/'SERVICE.json',{'pid':p.pid,'command':cmd});put(root/'RELAUNCH.json',{'command':cmd,'automatic_retry':False,'recovery':'inspect original process and output before any explicit new consumer generation'})
def consume(path,pin):
 need(sha(path)==pin,'plan changed');d=read(path);root=Path(d['out'])/'cpu';root.mkdir(exist_ok=True);lock=(root/'writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);need(not (root/'EXIT.json').exists(),'CPU terminal already exists');rc=1;stop=threading.Event()
 def beat():
  while not stop.wait(30):put(root/'heartbeat.json',{'utc_seconds':time.time(),'state':'comparing_operands'})
 t=threading.Thread(target=beat,daemon=True);t.start()
 try:
  R=module(d['modules']['runtime']);d,rows=R.verify(path,pin,host=True);cost=lifecycle(d,pin);B=module(d['modules']['backend']);result=B.compare_all(d,rows);result.update(cost);result.update(plan_sha256=pin,performance_accepted=False);put(root/'report.json',result);rc=0
 finally:stop.set();t.join(2);put(root/'EXIT.json',{'exit_code':rc,'plan_sha256':pin,'scientific_acceptance':False,'test_read':False,'utc_seconds':time.time()})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('op',choices=['consume']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);a=p.parse_args();consume(a.plan,a.sha256)
