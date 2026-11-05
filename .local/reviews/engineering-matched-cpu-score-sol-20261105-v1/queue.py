"""Detached serial Docker API queue, terminal-event waits, 600 s marker fallback."""
import socket,http.client,json,pathlib,time,os,hashlib,traceback,threading,statistics
R=pathlib.Path(__file__).resolve().parent;P=json.loads((R/'RUN-PINS.json').read_text());stop=threading.Event();state={'phase':'starting','completed':0,'total':6};seq=['baseline','candidate','candidate','baseline','baseline','candidate']
def put(n,v):
 p=R/n;t=p.with_name(p.name+'.pending');t.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n');os.replace(t,p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Unix(http.client.HTTPConnection):
 def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect('/var/run/docker.sock')
def api(method,path,obj=None,timeout=50):
 c=Unix('localhost',timeout=timeout);c.request(method,'/v1.44'+path,None if obj is None else json.dumps(obj),{'Content-Type':'application/json'});r=c.getresponse();b=r.read();c.close()
 if r.status>=400:raise RuntimeError(str(r.status)+' '+b.decode()[:500])
 return json.loads(b) if b else None

def digest():
 while not stop.wait(20):
  put('digest.json',{**state,'utc':time.time()});(R/'digest.md').write_text('Matched CPU score: '+json.dumps(state)+'\n');print(json.dumps(state),flush=True)
threading.Thread(target=digest,daemon=True).start()
def execute(name,label,directory,mode):
 image=P['images'][label];D=R/directory;D.mkdir(exist_ok=True)
 cfg={**P['source_config'],'output':str(D/'output')};(D/'config.json').write_text(json.dumps(cfg,sort_keys=True,indent=2)+'\n')
 conf={'Image':image,'Entrypoint':['python3','-B','-P',str(R/'instrument.py')],'Cmd':[str(D),mode], 'Env':['OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','VECLIB_MAXIMUM_THREADS=1','BLIS_NUM_THREADS=1','TORCH_DEVICE_BACKEND_AUTOLOAD=0','HF_HUB_OFFLINE=1','TRANSFORMERS_OFFLINE=1'],'HostConfig':{'Runtime':'runc','NetworkMode':'none','ReadonlyRootfs':True,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'NanoCpus':8000000000,'Memory':12884901888,'PidsLimit':256,'Binds':['/mnt/cephfs:/mnt/cephfs:ro',str(R)+':'+str(R)+':rw'],'Tmpfs':{'/tmp':'rw,noexec,nosuid,size=256m'},'AutoRemove':False,'RestartPolicy':{'Name':'no'}}}
 put(directory+'/LAUNCH.json',{'name':name,'config':conf,'config_sha256':sha(D/'config.json')})
 # Existing completed stages are validated, never silently rerun or overwritten.
 existing=api('GET','/containers/json?all=true&filters='+__import__('urllib.parse',fromlist=['quote']).quote(json.dumps({'name':['^/'+name+'$']})))
 if existing:
  cid=existing[0]['Id'];assert (D/'MEASURED-EXIT.json').exists(),'incomplete retained stage: inspect before resume'
 else:
  cid=api('POST','/containers/create?name='+name,conf)['Id'];t0=time.monotonic();api('POST','/containers/'+cid+'/start');started=time.monotonic()
  put(directory+'/START.json',{'id':cid,'start_monotonic':t0,'container_start_api_seconds':started-t0,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
  while True:
   try:wait=api('POST','/containers/'+cid+'/wait?condition=not-running',timeout=600);break
   except (TimeoutError,socket.timeout):
    # No agent polling: bounded controller fallback to the durable wrapper terminal.
    if (D/'MEASURED-EXIT.json').exists():wait={'StatusCode':json.loads((D/'MEASURED-EXIT.json').read_text())['exit_code']};break
  put(directory+'/WAIT.json',{'event':wait,'observed_monotonic':time.monotonic(),'total_to_terminal_seconds':time.monotonic()-t0})
 x=api('GET','/containers/'+cid+'/json');h=x['HostConfig'];put(directory+'/INSPECT.json',{k:x[k] for k in ['Id','Name','Image','State','Mounts']}|{'host':{k:h.get(k) for k in ['Runtime','NetworkMode','Devices','DeviceRequests','Privileged','ReadonlyRootfs','AutoRemove','NanoCpus','Memory','PidsLimit','Binds','SecurityOpt','CapDrop']},'environment_names':[e.split('=',1)[0] for e in x['Config']['Env']]})
 assert x['Image']==image
 assert json.loads((D/'MEASURED-EXIT.json').read_text())['exit_code']==0
 if mode!='warmup':
  terminal=json.loads((D/'output/EXIT.json').read_text());assert terminal['exit_code']==0 and terminal['manifest_sha256']==P['manifest_sha256'] and terminal['config_sha256']==sha(D/'config.json')
  report=json.loads((D/'output/report.json').read_text());assert report['records']==46320
  assert sha(D/'output/summary.json')==P['summary_sha256']
  assert terminal['summary_sha256']==P['summary_sha256']==report['summary_sha256']
 return D
rc=1
try:
 # Admit only the pinned accepted source; no discovery and no source writes.
 assert sha(pathlib.Path(P['source_config']['manifest']))==P['manifest_sha256']
 execute('nga-matched-cpu-sol-20261105-v1-warmup','baseline','warmup','warmup')
 rows=[]
 for i,label in enumerate(seq,1):
  state.update(phase=label,run=i);d=execute('nga-matched-cpu-sol-20261105-v1-'+str(i),label,'run'+str(i),'score')
  r=json.loads((d/'RESOURCE.json').read_text());report=json.loads((d/'output/report.json').read_text());wait=json.loads((d/'WAIT.json').read_text())
  row={'run':i,'condition':label,'image':P['images'][label],'summary_sha256':sha(d/'output/summary.json'),'config_sha256':sha(d/'config.json'),'manifest_sha256':P['manifest_sha256'],'reported_score_elapsed_seconds':report['elapsed_seconds'],'total_to_terminal_seconds':wait['total_to_terminal_seconds'],**r};rows.append(row);state['completed']=i;put('RUNS.json',rows)
 def stats(xs):return {'median':statistics.median(xs),'min':min(xs),'max':max(xs)}
 pairs=[]
 for a,b in [(0,1),(3,2),(4,5)]:
  B,C=rows[a],rows[b];pairs.append({'baseline_run':B['run'],'candidate_run':C['run'],'baseline_seconds':B['total_to_terminal_seconds'],'candidate_seconds':C['total_to_terminal_seconds'],'baseline_over_candidate':B['total_to_terminal_seconds']/C['total_to_terminal_seconds'],'reported_baseline_over_candidate':B['reported_score_elapsed_seconds']/C['reported_score_elapsed_seconds']})
 result={'status':'PASS_EXACT_SAVED_SCORER_CPU_BENCHMARK','scope':'engineering saved-result replay only; whole-base performance gate unqualified; research HOLD unchanged','runs':rows,'pairs':pairs,'per_condition':{l:{k:stats([r[k] for r in rows if r['condition']==l]) for k in ['total_to_terminal_seconds','child_elapsed_seconds','reported_score_elapsed_seconds','user_cpu_seconds','system_cpu_seconds','max_rss_kib']} for l in ['baseline','candidate']},'paired_ratios':stats([p['baseline_over_candidate'] for p in pairs]),'uninstrumented_phases':{k:None for k in ['config_admission','source_hash','population_validation','record_loading','parallel_arithmetic','aggregation','atomic_publish']},'cache':'bounded shared requests warmup only; no flush; unknown record residency; later runs may benefit from cache','physical_io_bytes':None}
 put('RESULT.json',result);rc=0;state.update(phase='complete',completed=6)
except BaseException as e:
 put('FAILURE.json',{'error':str(e),'traceback':traceback.format_exc(),'state':state});state['phase']='failed'
finally:
 put('digest.json',state);(R/'digest.md').write_text(json.dumps(state)+'\n');put('TERMINAL.json',{'exit_code':rc,'utc':time.time(),'state':state});stop.set()
