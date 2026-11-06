#!/usr/bin/env python3
"""Finite host dispatcher. Run only after independent review; never preempts workloads."""
import concurrent.futures, datetime, fcntl, importlib.util, json, os, re, subprocess, sys, threading, time, traceback
from pathlib import Path
R=Path(__file__).resolve().parent
def trusted(name):
 spec=importlib.util.spec_from_file_location(name,R/(name+'.py')); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
P=trusted('producer'); HP=trusted('host_ownership_probe')
C=P.CONFIG; ROOT=Path(C['root']); OUT=ROOT/'matched-k0-clean-dev'; ADAPTER=ROOT/'followup-cpu-separated-rc1'
DEFAULT_RESOURCE={'jobs': [{'id': '08b-k0', 'chip': 4, 'lane': 'q4b-s2', 'dependency_chip': 4, 'train_config': '70d1cb768b290041624bcb0541d903b6f8631e90eed2e3ae4c5a3e2936224607', 'dev_model': '4b-k0'}, {'id': '2b-k0', 'chip': 5, 'lane': 'q4b-s3', 'dependency_chip': 5, 'train_config': '465368bf1e0e24293faf6364ab2da38b146025dbe12bc153f98dbff24472860e', 'dev_model': '4b-k0'}, {'id': '4b-k0', 'chip': 6, 'lane': 'q9b-s2', 'dependency_chip': 6, 'train_config': '1e3f4642fc7d1ac8e58e359fa1c712eebab53ae746ddf732a354834ed4b9f8d3', 'dev_model': '9b-k0'}, {'id': '9b-k0', 'chip': 7, 'lane': 'q9b-s3', 'dependency_chip': 7, 'train_config': 'cfc782f53365994b42eacd5b89aa9a052074873cb3efc0876b9ef7604b87902d', 'dev_model': '9b-k0'}]}
RESOURCE=json.loads((R/'resource.json').read_text()) if (R/'resource.json').exists() else DEFAULT_RESOURCE
P.require(set(RESOURCE)=={'jobs'} and len(RESOURCE['jobs'])==4,'resource config')
P.require({x['id'] for x in RESOURCE['jobs']}=={x['id'] for x in C['models']},'resource roster')
P.require(all(set(x)=={'id','chip','lane','dependency_chip','train_config','dev_model'} and type(x['chip']) is int and x['chip'] in range(8) and type(x['dependency_chip']) is int and x['dependency_chip'] in range(8) and re.fullmatch('[a-f0-9]{64}',x['train_config']) and x['dev_model'] in {m['id'] for m in C['models']} for x in RESOURCE['jobs']),'resource entries')
P.require(len({x['chip'] for x in RESOURCE['jobs']})==4 and len({x['lane'] for x in RESOURCE['jobs']})==4,'duplicate resource')
JOBS=[(x['id'],x['chip'],x['lane']) for x in RESOURCE['jobs']]
TRAIN_CONFIG={x['lane']:x['train_config'] for x in RESOURCE['jobs']}
DEV_MODEL={x['lane']:x['dev_model'] for x in RESOURCE['jobs']}
DEPENDENCY_CHIP={x['lane']:x['dependency_chip'] for x in RESOURCE['jobs']}
DEADLINE=time.monotonic()+7*24*3600
CPU_SLOTS=threading.BoundedSemaphore(2)


def command(*x):return subprocess.run(x,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.strip()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def inspect(cid):return json.loads(command('docker','inspect',cid))[0]
def terminal(cid,chip,name):
 P.require(isinstance(cid,str) and re.fullmatch('[a-f0-9]{64}',cid),'invalid container id')
 i=inspect(cid);s=i['State'];h=i['HostConfig']
 P.require(i['Id']==cid and i['Name']=='/'+name and h.get('AutoRemove') is False and any(d.get('PathOnHost')=='/dev/davinci'+str(chip) for d in h.get('Devices') or []),'dependency container binding')
 if s['Status'] in ('running','created','paused','restarting'):return False
 P.require(s['Status']=='exited' and type(s['ExitCode']) is int and s['ExitCode']==0,'dependency terminal failure');return True

def retained_exit(launch,terminal_path):
 if not launch.is_file() or not terminal_path.is_file():return False
 l=json.loads(launch.read_text());t=json.loads(terminal_path.read_text());cid=l['container_id'];i=inspect(cid);s=i['State']
 P.require(t['container_id']==cid and t.get('container_exit_code')==0 and t['exit_code']==0 and s.get('Status')=='exited' and s['ExitCode']==0 and i['HostConfig'].get('AutoRemove') is False,'retained exit mismatch');return True

def ready(lane,chip):
 train=ROOT/lane;dev=ADAPTER/('full-'+lane);launch=train/'train-LAUNCH.json';done=train/'COMPLETE.json'
 if not launch.is_file():return False
 l=json.loads(launch.read_text());P.require(l.get('phase')=='train' and l.get('chip')==chip and l.get('config_sha256')==TRAIN_CONFIG[lane],'train receipt binding')
 if not terminal(l['container_id'],chip,'nga-rc1-'+lane+'-train'):return False
 if not done.is_file():return False
 P.require(json.loads(done.read_text())=={'exit_code':0,'steps':3116,'scientific_acceptance':False},'train completion')
 paths=[dev/'infer-LAUNCH.json',dev/'infer-EXIT.json',dev/'infer-BINDING.json',dev/'result/INFERENCE-READY.json',dev/'infer-COMMAND.json']
 if not all(p.is_file() for p in paths):return False
 launch,exit_,binding,h,devcmd=(json.loads(p.read_text()) for p in paths)
 P.require(launch.get('chip')==chip and launch.get('container_id')==exit_.get('container_id') and type(exit_.get('exit_code')) is int and exit_['exit_code']==0 and exit_.get('container_exit_code')==0,'DEV exit receipt')
 if not terminal(launch['container_id'],chip,'nga-rc1-cpu-full-'+lane+'-infer'):return False
 model=next(x['model'] for x in C['models'] if x['id']==DEV_MODEL[lane]);adapter=str(train/'result/adapter');pub=train/'result/adapter/PUBLICATION.json';bind=train/'result/adapter/BINDING.json'
 P.require(pub.is_file() and bind.is_file(),'DEV publication absent')
 publication=json.loads(pub.read_text());bound=json.loads(bind.read_text())
 P.require(binding.get('binding')==bound==publication.get('binding') and binding.get('publication_sha256')==P.sha(pub) and bound.get('owner')=='rc1-functional-'+lane,'DEV publication binding')
 P.require(launch.get('command_sha256')==P.sha(paths[4]) and isinstance(devcmd,list) and '--model' in devcmd and '--adapter' in devcmd and devcmd[devcmd.index('--model')+1]==model['path'] and devcmd[devcmd.index('--adapter')+1]==adapter and '--phase' in devcmd and devcmd[devcmd.index('--phase')+1]=='infer' and '--smoke' not in devcmd,'DEV command binding')
 P.require(h.get('version')==1 and h.get('model')==model['path'] and h.get('adapter')==adapter and h.get('out')=='/run/output/result' and h.get('limit')==0 and h.get('inference_header',{}).get('stages')=='k_score','DEV artifact binding')
 P.require(h['inference_header'].get('model',{}).get('base_path')==model['base_path'] and h['inference_header']['model'].get('base_revision')==model['base_revision'],'DEV model identity')
 return True

def free(chip):
 P.require(chip in [j[1] for j in JOBS],'unconfigured chip')
 probe=HP.check([chip]);P.require(probe.get('certain') is True,'host ownership uncertain');return not probe['unmanaged_owners']

def reviewed():
 p=OUT/'REVIEW-APPROVED.json'
 if not p.is_file():return False
 x=json.loads(p.read_text());artifact=Path(x.get('review_artifact','/nonexistent'));return x.get('verdict')=='pass' and artifact.is_file() and x.get('review_artifact_sha256')==P.sha(artifact) and all(x.get(n.replace('.','_')+'_sha256')==P.sha(R/n) for n in (('queue.py','producer.py','config.json','compare_dev.py','host_ownership_probe.py') + (('resource.json',) if (R/'resource.json').exists() else ())))

def artifact_evidence(mid,result,phase):
 receipt=result/'INFERENCE-READY.json';h=json.loads(receipt.read_text());model=next(x for x in C['models'] if x['id']==mid)
 P.require(h.get('version')==1 and h.get('model_id')==mid and h.get('out')==str(result) and h.get('config_sha256')==P.sha(R/'config.json') and h.get('groups')==P.GROUPS,'inference artifact binding')
 P.check_identity(h['identity'],{**model['model'],'weight_shard_pins':model['weight_shard_pins']});P.check_header(h['inference_header'],model['model'],h['descriptor'])
 P.require(set(h['stores'])==set(P.GROUPS),'store groups')
 for group,n in zip(P.GROUPS,P.COUNTS):
  suite,part,kind=group.split('/');store=result/'trackk'/(suite+'__'+part)/(kind+'.jsonl');ev=h['stores'][group]
  P.require(ev=={'store_sha256':P.sha(store),'receipt_sha256':P.sha(str(store)+'.receipt.json'),'rows':n},'store binding '+group)
 evidence={'inference_sha256':P.sha(receipt),'stores':h['stores']}
 if phase=='score':
  report=result/'clean-report.json';r=json.loads(report.read_text())
  P.require(r.get('schema')=='matched-k0-clean-dev-v1' and r.get('model_id')==mid and r.get('identity')==h['identity'] and r.get('inference_receipt_sha256')==evidence['inference_sha256'] and r.get('stores')==h['stores'] and r.get('inference_header')==h['inference_header'],'report binding')
  evidence['report_sha256']=P.sha(report)
 return evidence
def verify_sources():
 manifest=Path(C['closure'])/'manifest.json';P.require(P.sha(manifest)=='69ec7d7c78df080eff6645393a00c6ab3b485fd16e5f99a5c347dc866354b64a','closure manifest')
 for v in json.loads(manifest.read_text())['code'].values():P.require(P.sha(v['snapshot'])==v['sha256'],'closure '+v['snapshot'])
 for p,h in C['data_pins'].items():P.require(P.sha(p)==h,'data '+p)
def phase(mid,chip,phase):
 d=OUT/mid;d.mkdir(parents=True,exist_ok=True);name='nga-rc1-matched-k0-'+mid+'-'+phase;launch=d/(phase+'-LAUNCH.json');term=d/(phase+'-EXIT.json');result=d/'result'
 model=next(x['model']['path'] for x in C['models'] if x['id']==mid)
 mounts=[(str(R),'/run/packet',True),(C['closure'],C['closure'],True),(C['closure']+'/r0_code','/mnt/cephfs/xingchao/experiments/jev/r0_code',True),(model,model,True),('/usr/local/Ascend/driver','/usr/local/Ascend/driver',True),(str(d),str(d),False)]
 kev='/mnt/cephfs/xingchao/experiments/jev/KEV'
 for f in ['manifest.json','decision-v7/train.jsonl','decision-v7/calibration.jsonl','decision-v7/dev.jsonl','decision-v7/dev.variants.jsonl','transfer-v4/dev.jsonl','transfer-v4/dev.variants.jsonl']:mounts.append((kev+'/'+f,kev+'/'+f,True))
 cmd=['docker','run','-d','--pull=never','--name',name,'--label','nga.rc1.matched-k0='+mid,'--runtime','runc','--network','none','--shm-size','16g']
 if phase=='infer':
  for dev in ('davinci_manager','devmm_svm','hisi_hdc','davinci'+str(chip)):cmd+=['--device','/dev/'+dev]
 else:cmd+=['--cpus','4']
 for a,b,ro in mounts:cmd+=['--mount','type=bind,src='+a+',dst='+b+(',readonly' if ro else '')]
 for k,v in {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','MKL_NUM_THREADS':'4',**({'ASCEND_RT_VISIBLE_DEVICES':'0'} if phase=='infer' else {})}.items():cmd+=['-e',k+'='+v]
 setup='source /usr/local/Ascend/ascend-toolkit/set_env.sh; source /usr/local/Ascend/cann-9.2.0/share/info/ascendnpu-ir/bin/set_env.sh; source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi=1; export PYTHONPATH=/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe; exec python3 -B -P /run/packet/producer.py "$@"'
 cmd+=['--entrypoint','/bin/bash',C['image'],'-c',setup,'--','--phase',phase,'--model-id',mid,'--out',str(result)]
 cp=d/(phase+'-COMMAND.json')
 if launch.exists():P.require(cp.exists() and json.loads(cp.read_text())==cmd,'command mismatch');cid=json.loads(launch.read_text())['container_id']
 else:
  P.require(not term.exists(),'terminal without launch; manual reconciliation required')
  P.require(subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'unreceipted container');P.save(cp,cmd);verify_sources();P.require(reviewed(),'review pin missing or stale');
  if phase=='infer':
   owner=next(j[2] for j in JOBS if j[0]==mid and j[1]==chip);P.require(ready(owner,DEPENDENCY_CHIP[owner]) and free(chip),'dependency or chip no longer ready')
  cid=command(*cmd);P.save(launch,{'container_id':cid,'command_sha256':P.sha(cp),'chip':chip if phase=='infer' else None,'started':utc()})
 i=inspect(cid);P.require(i['Name']=='/'+name and i['Image']==C['image'] and i['Config']['Labels'].get('nga.rc1.matched-k0')==mid and json.loads(launch.read_text())['command_sha256']==P.sha(cp),'container binding')
 if term.exists():
  P.require(retained_exit(launch,term),'terminal mismatch');P.require(json.loads(term.read_text()).get('artifact_evidence')==artifact_evidence(mid,result,phase),'terminal artifact mismatch');return
 with (d/(phase+'-run.log')).open('a') as log:
  logger=subprocess.Popen(['docker','logs','--follow',cid],stdout=log,stderr=subprocess.STDOUT);code=int(command('docker','wait',cid));logger.wait(timeout=30)
 i=inspect(cid);P.require(i['State']['ExitCode']==code and i['State']['Status']=='exited' and i['HostConfig'].get('AutoRemove') is False,'exit mismatch')
 try:
  P.require(code==0,'container failed');evidence=artifact_evidence(mid,result,phase)
 except Exception:
  P.save(term,{'container_id':cid,'exit_code':1,'container_exit_code':code,'finished_at':i['State']['FinishedAt']});raise
 P.save(term,{'container_id':cid,'exit_code':0,'container_exit_code':code,'finished_at':i['State']['FinishedAt'],'artifact_evidence':evidence})

def lane(mid,chip,owner):
 if not (OUT/mid/'infer-LAUNCH.json').exists():
  while time.monotonic()<DEADLINE:
   if ready(owner,DEPENDENCY_CHIP[owner]) and free(chip):break
   time.sleep(600)
  else:raise TimeoutError('resource readiness deadline')
 phase(mid,chip,'infer')
 with CPU_SLOTS:phase(mid,chip,'score')
 return 'complete'
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/'queue.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);P.require(reviewed(),'independent review required');P.require(not (OUT/'QUEUE-EXIT.json').exists(),'queue terminal exists; inspect before relaunch');P.save(OUT/'QUEUE-LAUNCH.json',{'pid':os.getpid(),'utc':utc(),'queue_sha256':P.sha(__file__),'config_sha256':P.sha(R/'config.json')});results={};stop=threading.Event()
  def heartbeat():
   while not stop.wait(60):P.save(OUT/'heartbeat.json',{'utc':utc(),'completed':len(results),'total':4})
  threading.Thread(target=heartbeat,daemon=True).start()
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   fs={pool.submit(lane,*j):j[0] for j in JOBS}
   for f in concurrent.futures.as_completed(fs):
    try:results[fs[f]]=f.result()
    except Exception as e:results[fs[f]]='FAILED: '+str(e);P.save(OUT/(fs[f]+'-ERROR.json'),{'error':str(e),'traceback':traceback.format_exc()})
    P.save(OUT/'digest.json',{'utc':utc(),'results':results})
  stop.set();code=0 if all(x=='complete' for x in results.values()) and len(results)==4 else 1;P.save(OUT/'QUEUE-EXIT.json',{'exit_code':code,'results':results});return code
if __name__=='__main__':sys.exit(main())
