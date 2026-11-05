"""External process timing; accepted scorer image files remain unchanged."""
import os,json,pathlib,time,subprocess,resource,threading,hashlib,sys
D=pathlib.Path(sys.argv[1]); cfg=D/'config.json'
def put(n,v):
 p=D/n;t=p.with_suffix(p.suffix+'.pending');t.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n');os.replace(t,p)
def snapshot():
 r={'utc':time.time(),'monotonic':time.monotonic(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'loadavg':pathlib.Path('/proc/loadavg').read_text().strip(),'cpu_count':os.cpu_count(),'sched_affinity':sorted(os.sched_getaffinity(0)),'cpu_stat':pathlib.Path('/proc/stat').read_text().splitlines()[0]}
 for k in ['cpu','io','memory']:
  p=pathlib.Path('/proc/pressure')/k;r['psi_'+k]=p.read_text() if p.exists() else None
 return r
if sys.argv[2]=='warmup':
 m=json.loads(pathlib.Path(json.loads(cfg.read_text())['manifest']).read_text());p=pathlib.Path(m['population']['requests']['path']);t=time.monotonic()
 with p.open('rb') as f:b=f.read(16*1024*1024)
 put('WARMUP.json',{'path':str(p),'max_bytes':16*1024*1024,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'elapsed_seconds':time.monotonic()-t,'cache':'one bounded shared requests read; record cache residency unknown; no flush'})
 put('MEASURED-EXIT.json',{'exit_code':0});sys.exit(0)
before=snapshot();put('HOST-BEFORE.json',before);start=time.monotonic();stop=threading.Event();proc=None;samples=[]
def beat():
 while not stop.wait(10):
  h=D/'output/heartbeat.json'
  try:hb=json.loads(h.read_text()) if h.exists() else {'phase':'startup','completed':0,'total':46320}
  except (ValueError,OSError):continue
  s={'utc':time.time(),'monotonic':time.monotonic(),'phase':hb['phase'],'completed':hb['completed'],'total':hb['total']}
  if proc:
   try:s['proc_io']={k:int(v) for k,v in (line.split(':') for line in pathlib.Path('/proc',str(proc.pid),'io').read_text().splitlines())}
   except (OSError,ValueError):s['proc_io']=None
  samples.append(s);put('WRAPPER-heartbeat.json',s);print(json.dumps(s),flush=True)
thread=threading.Thread(target=beat,daemon=True);thread.start()
with (D/'score.log').open('ab',buffering=0) as log:
 proc=subprocess.Popen(['/opt/nga/entrypoint.sh',str(cfg)],stdout=log,stderr=subprocess.STDOUT)
 rc=proc.wait()
elapsed=time.monotonic()-start;stop.set();thread.join();r=resource.getrusage(resource.RUSAGE_CHILDREN)
put('RESOURCE.json',{'child_elapsed_seconds':elapsed,'user_cpu_seconds':r.ru_utime,'system_cpu_seconds':r.ru_stime,'max_rss_kib':r.ru_maxrss,'minor_faults':r.ru_minflt,'major_faults':r.ru_majflt,'voluntary_context_switches':r.ru_nvcsw,'involuntary_context_switches':r.ru_nivcsw,'logical_read_bytes':None if not samples or not samples[-1].get('proc_io') else samples[-1]['proc_io']['rchar'],'logical_read_note':'last 10-second process sample, incomplete; logical bytes are not physical I/O or Ceph traffic','physical_io_bytes':None,'start_monotonic':start,'end_monotonic':start+elapsed})
put('RESOURCE-SAMPLES.json',samples);put('HOST-AFTER.json',snapshot());put('MEASURED-EXIT.json',{'exit_code':rc,'utc':time.time(),'monotonic':time.monotonic()});sys.exit(rc if rc>=0 else 128-rc)
