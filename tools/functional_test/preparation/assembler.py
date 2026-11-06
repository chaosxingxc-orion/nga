#!/usr/bin/env python3
"""Produce immutable, unreviewed drafts against the accepted host stage."""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
STAGE=Path('/mnt/cephfs/xingchao/experiments/jev/rc1-host-stage-20261106-2600925')
sys.path.insert(0,str(STAGE))
import rc1_trackk as C, supervisor as H

def pin(p): return {'path':str(p),'sha256':C.sha(p)}
def assemble(roster_path, resources_path, campaign):
 rows=C.read(roster_path); resources=C.read(resources_path); ids=C.LANES+C.BASES
 C.require([r['id'] for r in rows]==ids,'roster order')
 C.require(set(resources)==set(ids),'resource roster')
 # No status inference: pending is never a failed or unavailable row.
 identities={}
 for r in rows:
  C.require(r['status'] in ('available','failed','unavailable'),'pending or invalid status')
  if r['status']!='available':
   C.require(isinstance(r.get('reason'),str) and bool(r['reason']) and isinstance(r.get('evidence'),dict) and bool(r['evidence']),'failure evidence required')
   for v in r['evidence'].values(): C.pinfile(v)
   continue
  k1=r['id'] in C.LANES; size=r['id'].split('-')[0]
  C.require(r.get('arm')==('K1' if k1 else 'K0') and r.get('size')==size,'role differs')
  C.require((r.get('seed')==int(r['id'][-1]) and r.get('terminal_step')==3116) if k1 else r.get('seed') is None,'seed or terminal differs')
  C.require((r.get('adapter') is not None)==k1,'adapter differs')
  keys={'base_inventory','tokenizer','runtime'} | ({'publication','training_terminal','smoke_resume','dev_review'} if k1 else set())
  C.require(keys <= set(r.get('evidence',{})),'missing evidence')
  for v in r['evidence'].values(): C.pinfile(v)
  with tempfile.TemporaryDirectory(prefix='rc1-ident-') as identity_dir:
   ident=C.TL.model_identity(r['model'],r['adapter'],identity_dir)
  C.require(ident['base_revision']!='unknown' and ident['sha256']==r['identity_sha256'],'identity differs')
  identities[r['id']]=ident['sha256']
 C.require(len(set(identities.values()))==len(identities),'duplicate identity')
 for size in ('q0p8b','q2b','q4b','q9b'):
  C.require(len({str(Path(r['model']).resolve()) for r in rows if r['status']=='available' and r['id'].startswith(size+'-')})<=1,'same-size base differs')
 for member,x in resources.items():
  C.require(set(x)=={'chip','dependencies'} and type(x['chip']) is int and 0<=x['chip']<8,'resource config')
  C.require(isinstance(x['dependencies'],list) and len(set(x['dependencies']))==len(x['dependencies']) and all(z in ('K0','27B') for z in x['dependencies']),'dependencies')
  C.require(('27B' if x['chip']<4 else 'K0') in x['dependencies'],'resource successor dependency missing')
 camp=Path(campaign).resolve(); camp.mkdir(parents=True,exist_ok=False)
 for p in ('round','state','configs','reviews','drafts','transactions','runs'): (camp/p).mkdir()
 rt=STAGE/'runtime-environment.json'; image=C.read(rt)['image']; entry=STAGE/'rc1_trackk.py'; source={p:C.sha(p) for p in sorted(C.required_sources())}
 host={'entry':str(entry),'state_dir':str(camp/'state'),'allocation':'/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json','owner':'rc1-trackk','dependency_policy':'wait-for-verified-free-resource','cpu_python':str(STAGE)+'-cpu/bin/python','cpu_environment':{'PATH':'/usr/bin:/bin','PYTHONPATH':str(STAGE),'PYTHONNOUSERSITE':'1'},'cpu_requires_numpy':True,'runtime_evidence':pin(rt),'matched_protocol':pin(STAGE/'experiments/RC1-MATCHED-K0.md'),'implementation_files':{str(p):C.sha(p) for p in [STAGE/'supervisor.py',*(STAGE/'tools'/n for n in ('r3_final_container.py','r3_resource_adapter.py','unified_resource_provider_v1.py','experiment_dag.py','unified_container_host_v1.py','unified_resource_lease_v1.py'))]},'r0_source_files':{str(p):C.sha(p) for p in sorted(H.R0.glob('*.py'))}}
 shared={'schema':'rc1-trackk-v1','protocol':pin(STAGE/'experiments/RC1-FUNCTIONAL-TEST.md'),'manifest':pin(Path(C.C.KEV_DIR)/'manifest.json'),'source_files':source,'image':image,'roster':rows,'round_dir':str(camp/'round'),'host':host}
 graph={'schema':'rc1-dispatch-graph-v1','campaign_sha256':C.campaign_digest(shared),'members':{},'roster_sha256':C.sha(roster_path),'resources_sha256':C.sha(resources_path)}
 for row in rows:
  member=row['id']; chip=resources[member]['chip']; out=camp/'runs'/member; out.mkdir(); trans=camp/'transactions'/member;trans.mkdir(); final=camp/'configs'/(member+'.json'); review=camp/'reviews'/(member+'.json')
  mounts={x:False for x in [*source,str(rt),host['matched_protocol']['path'],shared['protocol']['path'],shared['manifest']['path'],str(final),str(review),str(H.CLOSURE),str(H.R0)]}
  for s,p,suf in [('decision-v7','train',''),('decision-v7','calibration',''),('decision-v7','test',''),('decision-v7','test','.variants'),('transfer-v4','test',''),('transfer-v4','test','.variants')]: mounts[str(Path(C.C.KEV_DIR)/s/(p+suf+'.jsonl'))]=False
  for r in rows:
   if r['status']=='available':
    for x in [r['model'],r.get('adapter'),*[v['path'] for v in r['evidence'].values()]]:
     if x: mounts[x]=False
  mounts.update({str(out):True,str(camp/'round'):True})
  spec={'name':'rc1-test-'+member,'image':image,'cmd':[],'mounts':mounts,'devices':['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(chip)],'environment':{}}
  c={**shared,'member':member,'out':str(out),'container':{'spec':spec,'run':'rc1-'+member,'chip':chip,'claim':str(trans/'claim.json'),'release':str(trans/'release.json'),'launch_receipt':str(trans/'launch.json')}}
  template=camp/'drafts'/(member+'.input.json'); C.save(template,c); draft=camp/'drafts'/(member+'.json')
  subprocess.run([sys.executable,'-P',str(STAGE/'config_builder.py'),'--template',str(template),'--runtime',str(rt),'--entry',str(entry),'--config-path',str(final),'--output',str(draft)],check=True)
  graph['members'][member]={'draft':str(draft),'draft_sha256':C.sha(draft),'config':str(final),'review':str(review),'chip':chip,'dependencies':resources[member]['dependencies'],'status':row['status']}
 C.save(camp/'graph.json',graph)
 return graph

def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--resources',required=True);p.add_argument('--campaign',required=True);a=p.parse_args();g=assemble(a.roster,a.resources,a.campaign);print(json.dumps({'status':'needs_review','drafts':len(g['members']),'campaign_sha256':g['campaign_sha256']}))
if __name__=='__main__': main()
