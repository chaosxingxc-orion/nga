#!/usr/bin/env python3
"""Collect completed RC1 producer artifacts; polling never opens score stores."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

ROLES=[f'{s}-s{i}' for s in ('q0p8b','q2b','q4b','q9b') for i in (2,3)]+[f'{s}-base' for s in ('q0p8b','q2b','q4b','q9b')]
GROUPS=['decision-v7/calibration/clean']+[f'{s}/test/{k}' for s in ('decision-v7','transfer-v4') for k in ('clean','variants','question_only','empty_input')]
def read(p): return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def pin(p):
 p=str(Path(p).resolve()); return {'path':p,'sha256':sha(p)}
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def allpins(x):
 if isinstance(x,dict):
  if set(x)=={'path','sha256'}: yield x
  else:
   for k,v in x.items():
    if k!='authorized_files': yield from allpins(v)
 elif isinstance(x,list):
  for v in x: yield from allpins(v)
def inspect(cfg):
 result=[];common=None
 for name in ROLES:
  pending=[]; errors=[];p=Path(cfg['configs'].get(name,''))
  if not p.is_file(): result.append({'id':name,'status':'pending','missing':['config']});continue
  try:
   c=read(p); rows=c['roster']; role=next(r for r in rows if r['id']==name)
   if [r['id'] for r in rows]!=ROLES or any(r['status']!='available' for r in rows): raise ValueError('roster/order/status mismatch')
   if c['member']!=name or role['size']!=name.split('-')[0] or role['seed']!=(None if name.endswith('-base') else int(name[-1])) or role['terminal_step']!=(None if name.endswith('-base') else 3116): raise ValueError('wrong member/seed/terminal')
   shared={k:c[k] for k in ('schema','protocol','manifest','source_files','image','roster','round_dir')}
   if common is None: common=shared
   elif shared!=common: raise ValueError('campaign mismatch')
   out=Path(c['out']); rd=Path(c['round_dir']); ident=role['identity_sha256']
   paths={'config':p,'identity':Path(cfg['identities'][name]),'ready':out/'INFERENCE-READY.json','infer_exit':out/'INFER-EXIT.json','report':out/'K-REPORT.json','fit':out/'CPU/OPERATOR-FIT.json','final':rd/'FINAL.json','access':rd/'TEST-READS.log','owner':rd/('owner-'+ident+'.json'),'run_identity':out/'RUN_IDENTITY.json','producer_manifest':out/'manifests/main.json','host_release_verified':out/'HOST-RELEASE-VERIFIED.json'}
   if cfg['kind']=='production':
    for k in ('launch_receipt','claim','release'): paths[k]=Path(c['container'][k])
    paths['container_observation']=Path(cfg['observations'][name])
   pending=[k for k,v in paths.items() if not v.is_file()]
   if paths['infer_exit'].is_file():
    e=read(paths['infer_exit'])
    if e.get('exit_code')!=0 or e.get('schema')!='rc1-infer-exit-v1' or e.get('config_sha256')!=digest(c): raise ValueError('failed or mismatched infer terminal')
    if paths['ready'].is_file() and e.get('ready_sha256')!=sha(paths['ready']): raise ValueError('infer/ready contradiction')
   if paths['identity'].is_file() and read(paths['identity']).get('sha256')!=ident: raise ValueError('identity differs')
   if paths['ready'].is_file():
    ready=read(paths['ready']); owner={'config_sha256':digest(c),'model_sha256':ident,'out':c['out']}
    if ready.get('owner')!=owner or ready.get('groups')!=GROUPS: raise ValueError('ready owner/groups differs')
   if paths['report'].is_file() and paths['ready'].is_file():
    report=read(paths['report'])
    if report.get('inference_ready_sha256')!=sha(paths['ready']): raise ValueError('report/ready contradiction')
   if cfg['kind']=='production' and not any(k in pending for k in ('claim','release','launch_receipt','container_observation','host_release_verified','ready')):
    launch=read(paths['launch_receipt']);release=read(paths['release']);claim=read(paths['claim']);obs=read(paths['container_observation']);host=read(paths['host_release_verified']);state=obs['State'];container=c['container']
    if not (launch['id']==release['container_id']==obs['Id']==host['container_id'] and state['Status']=='exited' and state['ExitCode']==0 and not state.get('OOMKilled',False) and release['exit_code']==0 and release['container_started_at']==state['StartedAt'] and release['container_finished_at']==state['FinishedAt'] and claim['run']==release['run']==container['run'] and claim['chip']==release['chip']==container['chip'] and release['claim_sha256']==sha(paths['claim']) and host['release_sha256']==sha(paths['release']) and host['ready_sha256']==sha(paths['ready'])): raise ValueError('host receipt/container identity contradiction')
   result.append({'id':name,'status':'pending' if pending else 'complete','missing':pending,'paths':{k:str(v.resolve()) for k,v in paths.items()}})
  except (ValueError,KeyError,TypeError,StopIteration,json.JSONDecodeError) as ex: result.append({'id':name,'status':'error','error':str(ex)})
 return result

def build(cfg,out):
 rows=inspect(cfg)
 if any(x['status']!='complete' for x in rows): return {'status':'pending' if all(x['status']!='error' for x in rows) else 'error','roles':rows}
 c=read(cfg['configs'][ROLES[0]]);members={x['id']:{k:pin(v) for k,v in x['paths'].items()} for x in rows}
 packet={'schema':'rc1-same-test-packet-v1','kind':cfg['kind'],'fixture_only':cfg['kind']=='generated','roster':c['roster'],'members':members,'producer':pin(cfg['producer']),'bootstrap_wrapper':pin(cfg['bootstrap_wrapper']),'source_files':c['source_files'],'module_dirs':cfg['module_dirs'],'populations':{k:pin(v) for k,v in cfg['populations'].items()},'data_pins':cfg['data_pins'],'image':c['image'],'protocol':c['protocol'],'manifest':c['manifest']}
 if cfg.get('reference_context'):packet['reference_context']={'mapping_metadata':pin(cfg['reference_context'])}
 auth={p['path']:p['sha256'] for p in allpins(packet)};auth.update(c['source_files'])
 for name in ROLES:
  member=read(cfg['configs'][name]);review=member['review'];auth[review['path']]=review['sha256']; ready=read(members[name]['ready']['path'])
  for group in GROUPS:
   suite,partition,kind=group.split('/');path=str(Path(member['out'])/'trackk'/f'{suite}__{partition}'/(kind+'.jsonl'));e=ready['stores'][group]
   for p,h in ((path,e['store_sha256']),(path+'.receipt.json',e['receipt_sha256'])):
    if sha(p)!=h: raise ValueError('saved store/receipt differs: '+p)
    auth[p]=h
 packet['authorized_files']=auth;out=Path(out);save(out/'packet.json',packet)
 bindings={r['id']:{k:r[k] for k in ('identity_sha256','model','adapter','evidence')} for r in c['roster']}
 review_input={'schema':'rc1-numerical-completed-access-review-v1','packet_sha256':sha(out/'packet.json'),'new_test_access':False,'scope':'reconstruct-authorized-saved-vectors-only','source_acceptance':cfg.get('source_acceptance'),'authorized_files':auth,'model_bindings':bindings}
 save(out/'review-input.json',review_input)
 cc={'schema':'rc1-same-test-consumer-v1','packet':pin(out/'packet.json'),'allow_generated':cfg['kind']=='generated','allow_production':cfg['kind']=='production','workers':cfg.get('workers',2)}
 for k in ('reference_metadata','reference_performance_export','source_acceptance'):
  if cfg.get(k):cc[k]=cfg[k]
 if cfg['kind']=='production':
  review=cfg.get('completed_access_review')
  if review and Path(review).is_file():cc['completed_access_review']=pin(review)
 save(out/'consumer-config.json',cc)
 return {'status':'ready_for_review' if cfg['kind']=='production' and 'completed_access_review' not in cc else 'ready_for_consumer','packet':str(out/'packet.json'),'roles':rows}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['inspect','build','consume']);ap.add_argument('--config',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();cfg=read(a.config)
 try:
  result={'status':'inventory','roles':inspect(cfg)} if a.mode=='inspect' else build(cfg,a.out)
  if a.mode=='consume' and result['status']=='ready_for_consumer':
   actual=sha(cfg['consumer']);
   if actual!=cfg['consumer_sha256']: raise ValueError('accepted consumer bytes differ')
   cmd=[cfg.get('python',sys.executable),'-B','-P',cfg['consumer'],'--config',str(Path(a.out)/'consumer-config.json'),'--out',str(Path(a.out)/'comparison')];r=subprocess.run(cmd);result['consumer_exit']=r.returncode
  save(Path(a.out)/'collector-status.json',result);print(json.dumps(result));return 1 if result['status']=='error' else (2 if result['status'] in ('pending','ready_for_review') else result.get('consumer_exit',0))
 except (OSError,ValueError,KeyError,TypeError) as e:
  save(Path(a.out)/'collector-status.json',{'status':'error','error':str(e)});print(str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
