#!/usr/bin/env python3
"""Produce immutable, unreviewed drafts against the accepted host stage."""
import argparse, importlib.util, json, subprocess, sys
from pathlib import Path
STAGE=Path('/mnt/cephfs/xingchao/experiments/jev/rc1-host-stage-20261106-2600925')
ENTRY_STAGE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ENTRY_STAGE))
import rc1_trackk as C
HOST=Path(__file__).resolve().parent
sys.path.insert(0,str(HOST))
import identity_reuse as IR
spec=importlib.util.spec_from_file_location('rc1_export_host',HOST/'supervisor.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)

def pin(p): return {'path':str(p),'sha256':C.sha(p)}
def assemble(roster_path, resources_path, campaign, inventory_pin, source_review_pin):
 ctx=IR.load_inventory(inventory_pin, source_review_pin)
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
  ident=IR.select(ctx,r)
  C.require(ident['base_revision']!='unknown' and ident['sha256']==r['identity_sha256'],'identity differs')
  identities[r['id']]=ident['sha256']
 C.require(len(set(identities.values()))==len(identities),'duplicate identity')
 for size in ('q0p8b','q2b','q4b','q9b'):
  C.require(len({str(Path(r['model']).resolve()) for r in rows if r['status']=='available' and r['id'].startswith(size+'-')})<=1,'same-size base differs')
 for member,x in resources.items():
  C.require(set(x)=={'chip','dependencies'} and type(x['chip']) is int and 0<=x['chip']<8,'resource config')
  C.require(isinstance(x['dependencies'],list) and len(set(x['dependencies']))==len(x['dependencies']) and all(z in ('K0','TRAIN_DEV','QWEN27B_ENVFIX') for z in x['dependencies']),'dependencies')
  C.require(set(['K0','QWEN27B_ENVFIX'] if x['chip']<4 else ['TRAIN_DEV']).issubset(x['dependencies']),'resource successor dependency missing')
 camp=Path(campaign).resolve(); camp.mkdir(parents=True,exist_ok=False)
 for p in ('round','state','configs','reviews','drafts','transactions','runs','dev'): (camp/p).mkdir()
 IR.seed_core_cache(C,camp/'round',ctx,[r for r in rows if r['status']=='available'])
 rt=STAGE/'runtime-environment.json'; image=C.read(rt)['image']; entry=ENTRY_STAGE/'rc1_trackk.py'; source={p:C.sha(p) for p in sorted(C.required_sources())}
 host={'entry':str(entry),'state_dir':str(camp/'state'),'allocation':'/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json','owner':'rc1-trackk','dependency_policy':'wait-for-verified-free-resource','cpu_python':str(STAGE)+'-cpu/bin/python','cpu_environment':{'PATH':'/usr/bin:/bin','PYTHONPATH':str(ENTRY_STAGE)+':'+str(STAGE),'PYTHONNOUSERSITE':'1'},'cpu_requires_numpy':True,'runtime_evidence':pin(rt),'matched_protocol':pin(STAGE/'experiments/RC1-MATCHED-K0.md'),'implementation_files':{str(p):C.sha(p) for p in [HOST/'supervisor.py',HOST/'config_builder.py',HOST/'exporter.py',HOST/'dev_binding.py',HOST/'identity_reuse.py',*(STAGE/'tools'/n for n in ('r3_final_container.py','r3_resource_adapter.py','unified_resource_provider_v1.py','experiment_dag.py','unified_container_host_v1.py','unified_resource_lease_v1.py'))]},'r0_source_files':{str(p):C.sha(p) for p in sorted(H.R0.glob('*.py'))}}
 shared={'schema':'rc1-trackk-v1','protocol':pin(STAGE/'experiments/RC1-FUNCTIONAL-TEST.md'),'manifest':pin(Path(C.C.KEV_DIR)/'manifest.json'),'source_files':source,'image':image,'roster':rows,'round_dir':str(camp/'round'),'host':host}
 graph={'schema':'rc1-dispatch-graph-v1','campaign_sha256':C.campaign_digest(shared),'members':{},'roster_sha256':C.sha(roster_path),'resources_sha256':C.sha(resources_path)}
 for row in rows:
  member=row['id']; dev=camp/'dev'/member; dev.mkdir(); chip=resources[member]['chip']; out=camp/'runs'/member; out.mkdir(); trans=camp/'transactions'/member;trans.mkdir(); final=camp/'configs'/(member+'.json'); review=camp/'reviews'/(member+'.json')
  mounts={x:False for x in [*source,str(rt),host['matched_protocol']['path'],shared['protocol']['path'],shared['manifest']['path'],str(final),str(review),str(H.CLOSURE),str(H.R0),str(dev)]}
  for s,p,suf in [('decision-v7','train',''),('decision-v7','calibration',''),('decision-v7','test',''),('decision-v7','test','.variants'),('transfer-v4','test',''),('transfer-v4','test','.variants')]: mounts[str(Path(C.C.KEV_DIR)/s/(p+suf+'.jsonl'))]=False
  for r in rows:
   if r['status']=='available':
    for x in [r['model'],r.get('adapter'),*[v['path'] for v in r['evidence'].values()]]:
     if x: mounts[x]=False
  mounts.update({str(out):True,str(camp/'round'):True})
  spec={'name':'rc1-test-'+member,'image':image,'cmd':[],'mounts':mounts,'devices':['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(chip)],'environment':{}}
  c={**shared,'host':{**host,'dev_evidence_dir':str(dev)},'member':member,'out':str(out),'container':{'spec':spec,'run':'rc1-'+member,'chip':chip,'claim':str(trans/'claim.json'),'release':str(trans/'release.json'),'launch_receipt':str(trans/'launch.json')}}
  if member==H.EXPORT_MEMBER:
   c['host']={**c['host'],'cpu_entry':str(HOST/'exporter.py')}
   c['population_export']={'producer':pin(entry),'exporter':pin(HOST/'exporter.py'),'member':member,'directory':str(camp/'population-export'),'scope':H.EXPORT_SCOPE}
  template=camp/'drafts'/(member+'.input.json'); C.save(template,c); draft=camp/'drafts'/(member+'.json')
  subprocess.run([sys.executable,'-P',str(HOST/'config_builder.py'),'--template',str(template),'--runtime',str(rt),'--entry',str(entry),'--config-path',str(final),'--output',str(draft)],check=True)
  graph['members'][member]={'draft':str(draft),'draft_sha256':C.sha(draft),'config':str(final),'review':str(review),'chip':chip,'dependencies':resources[member]['dependencies'],'status':row['status']}
 C.save(camp/'graph.json',graph)
 return graph

def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--resources',required=True);p.add_argument('--campaign',required=True);p.add_argument('--identity-inventory-pin',required=True,help='JSON file containing path/sha256');p.add_argument('--source-review-pin',required=True,help='JSON file containing path/sha256');a=p.parse_args();g=assemble(a.roster,a.resources,a.campaign,C.read(a.identity_inventory_pin),C.read(a.source_review_pin));print(json.dumps({'status':'needs_review','drafts':len(g['members']),'campaign_sha256':g['campaign_sha256']}))
if __name__=='__main__': main()
