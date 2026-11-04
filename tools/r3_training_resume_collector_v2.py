"""Recovered PT2 physical evidence collector; no independent/scientific acceptance."""
import datetime,json
from pathlib import Path
import types
import hashlib
_h=Path(__file__).with_name('r3_training_resume_handoff_v2.py');_raw=_h.read_bytes()
if hashlib.sha256(_raw).hexdigest()!='5e83cfe54594c4f1ac77691f7fa56d33cbb58a0accf6b62a756ee6466cf73df6':raise ValueError('handoff source changed')
_H=types.ModuleType('recovery_handoff');_H.__file__=str(_h);exec(compile(_raw,str(_h),'exec'),_H.__dict__)
need=_H.need;safe=_H.safe;sha=_H.sha;read=_H.read;ref=_H.ref;module=_H.module

SCHEMA='r3-training-resume-collector-v2'
def identity(path,pin):
 c=read(path,pin);need(c['schema']==SCHEMA and c['scientific_acceptance'] is False and c['test_read'] is False,'collector scope')
 need(ref(c['controller'])==Path(__file__).resolve(),'collector controller')
 H=module(c['handoff_controller']);need(c['handoff_controller']==read(ref(c['handoff']))['controller'],'handoff controller differs')
 b,p,j,base,binder=H.identity(c['handoff']['path'],c['handoff']['sha256'])
 L=module(c['legacy']);O=module(c['ownership'])
 need(c['legacy']['sha256']=='5b4f62baba6ab9588b4fabad95be995bebda6bd192fa0df2a525f845cb005c41' and c['ownership']['sha256']=='89fa709d4f830f38ebbc7bd449d89a8e3c527ed3e986dc71ff6faa64f755df4f','accepted primitives required')
 out=safe(c['output']);need(out.name.endswith('.json'),'output suffix')
 H.disjoint(Path(p['out']),Path(b['state_root']),out.parent)
 return c,H,b,p,j,base,binder,L,O

def predecessor(p,claim,load,hashfile):
 r=p['recovery'];q=r['resource_predecessor'];root=Path(q['out']);receipt=root/'attempts/1/LAUNCH_RECEIPT.json';cp=root/'attempts/1/CLAIM.json';rp=root/'attempts/1/RELEASE.json'
 need(hashfile(receipt)==q['receipt_sha256'] and hashfile(cp)==q['claim_sha256'],'QO generation changed')
 rec=load(receipt);cl=load(cp);rel=load(rp);pre=load(Path(p['out'])/'SUCCESSOR_PRECONDITION.json');hook=claim.get('successor_precondition',{})
 need(rec['id']==q['container_id']==rel['container_id'] and cl['chip']==rel['chip']==p['chip']==3 and cl['run']==rel['run'],'QO identity differs')
 need(rel['claim_sha256']==q['claim_sha256'] and pre['release_sha256']==hashfile(rp),'QO release differs')
 need(pre.get('plan_sha256')==_H.canonical(p) and pre.get('checkpoint_sha256')==r['checkpoint']['sha256'],'precondition plan/checkpoint differs')
 need(hook.get('schema')=='pt2-recovery-claim-v2' and hook.get('release_sha256')==hashfile(rp) and hook.get('container_id')==q['container_id'] and hook.get('checkpoint_sha256')==r['checkpoint']['sha256'] and hook.get('precondition_sha256')==hashfile(Path(p['out'])/'SUCCESSOR_PRECONDITION.json'),'claim recovery proof differs')
 actual=[x for x in claim['allocation_before']['free'] if x['chip']==3];expected=[x for x in rel['allocation_after']['free'] if x['chip']==3]
 need(actual==expected and len(actual)==1 and actual[0]['previous_run']==cl['run'] and actual[0]['release_evidence']==str(rp),'claim predecessor lineage differs')
 return {str(x):hashfile(x) for x in [receipt,cp,rp,Path(p['out'])/'SUCCESSOR_PRECONDITION.json']}

def container_check(L,p,j,actual,image,daemon):
 # Wrapper launcher intentionally contains no duplicated Docker-policy functions.
 r=p['recovery']['launcher_base'];api=L.extracted_launcher(r['path'],r['sha256'])
 need(daemon.get('DefaultRuntime') and daemon.get('CgroupVersion') in ('1','2'),'daemon missing')
 api['verify_control_resume_container'](p,j['training_plan']['path'],1,actual,image,daemon={'runtime':daemon['DefaultRuntime'],'cgroupns':'private' if daemon['CgroupVersion']=='2' else 'host'})
 api['verify_retained_receipts'](Path(p['out'])/'attempts/1',j['canonical_plan_sha256'],actual,api['docker_command'](p,j['training_plan']['path'],1))
 s=actual['State'];need(actual['Name']=='/'+p['container']+'-a1' and s['Status']=='exited' and s['Running'] is False and type(s['ExitCode']) is int and s['ExitCode']==0 and not s.get('OOMKilled') and not s.get('Error'),'retained training unsuccessful')

def collect(path,pin,observations,observation_pin):
 c,H,b,p,j,base,binder,L,O=identity(path,pin);cap=H.inspect(c['handoff']['path'],c['handoff']['sha256'],persist=True)
 if cap['status']!='REVIEW_REQUIRED':return cap
 state=Path(b['state_root']);cp=state/'CAPTURE.json';out=safe(c['output']);training=Path(p['out']);out.parent.mkdir(parents=True,exist_ok=True)
 need(not out.exists(),'collection exists; never overwrite')
 with L.owned_snapshot() as snap:
  L.ACTIVE=snap
  try:
   for r in [c['controller'],c['handoff'],c['handoff_controller'],c['legacy'],c['ownership'],b['training_plan'],b['training_review']]:snap.capture(r['path'],r['sha256'])
   snap.capture(path,pin);snap.capture(cp,sha(cp))
   for f,h in cap['files'].items():snap.capture(f,h,payload=Path(f).name=='adapter_model.safetensors')
   adapter=training/'adapter/adapter_model.safetensors';snap.inventory(adapter.parent)
   obs=safe(observations);need(not obs.is_relative_to(training) and not obs.is_relative_to(state),'observations inside producer')
   manifest=L.load(obs,pin=observation_pin);need(manifest['schema']=='r3-postrun-external-observations-v1' and manifest['training']==p['out'] and manifest['capture_sha256']==sha(cp) and set(manifest['observations'])=={'container','image','daemon'},'observation binding')
   docs={};opins={str(obs):observation_pin}
   for name,r in manifest['observations'].items():
    f=safe(r['path']);need(not f.is_relative_to(training) and not f.is_relative_to(state),'observation inside producer');docs[name]=L.load(f,pin=r['sha256']);opins[str(f)]=r['sha256']
   need(all(isinstance(docs[n],list) and len(docs[n])==1 for n in ('container','image')),'single observation')
   actual=docs['container'][0];container_check(L,p,j,actual,docs['image'][0],docs['daemon'])
   claim=L.load(training/'attempts/1/CLAIM.json');rel=L.load(training/'attempts/1/RELEASE.json')
   O.ownership(p,claim,rel,cap['files'][str(training/'attempts/1/CLAIM.json')],training/'attempts/1/RELEASE.json',actual)
   recovery_pins=predecessor(p,claim,L.load,L.sha)
   end=L.load(training/'TRAIN_EXIT.json');need(end==L.load(training/'attempts/1/EXIT.json') and end.get('source')!='retained-container-exit','genuine terminal')
   moment=lambda x:datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
   need(moment(actual['State']['StartedAt'])<=moment(end['started_utc'])<=moment(end['finished_utc'])<=moment(actual['State']['FinishedAt']),'driver chronology')
   for f,h in p['files'].items():snap.capture(f,h)
   for name in ['source_plan','checkpoint','original_checkpoint','cpu_binding','failed_release']:
    r=p['recovery'][name];snap.capture(r['path'],r['sha256'])
   m=L.load(training/'manifest.json');need(binder.semantic_arm(dict(p,arm='k1'),m)=='K1-PT','manifest control');L.verify_manifest(m,p)
   cfg=L.load(training/'adapter/adapter_config.json');L.verify_config(cfg,p['model']);payload=L.verify_payload(adapter,L.expected_shapes(p['model'],cfg));need(payload['scanned_sha256']==cap['files'][str(adapter)],'payload changed')
   need(H.capture(b,p,j,base,binder)==cap,'capture changed')
   result={'schema':'r3-recovery-postrun-collection-v1','status':'EVIDENCE_COLLECTED_REVIEW_REQUIRED','training':p['out'],'binding_sha256':b['_pin'],'capture_sha256':sha(cp),'files':cap['files'],'external_observation_pins':opins,'recovery_pins':recovery_pins,'adapter_payload':payload,'source_sha256':{f:e['sha256'] for f,e in snap.entries.items()},'independent_review_granted':False,'scientific_acceptance':False,'test_read':False}
   L.save(out,result,guard=snap.final_check);return result
  finally:L.ACTIVE=None

if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);a.add_argument('--observations',required=True);a.add_argument('--observations-sha256',required=True);v=a.parse_args()
 print(json.dumps({k:x for k,x in collect(v.config,v.sha256,v.observations,v.observations_sha256).items() if k not in ('files','source_sha256')},indent=2))
