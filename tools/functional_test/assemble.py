#!/usr/bin/env python3
"""Build unreviewed per-member drafts from an explicitly supplied complete roster."""
import argparse,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import rc1_trackk as C, supervisor as H

def pin(p): return {'path':str(p),'sha256':C.sha(p)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--roster',required=True);p.add_argument('--campaign',required=True);p.add_argument('--chip',type=int,required=True);a=p.parse_args()
 camp=Path(a.campaign).resolve(); camp.mkdir(parents=True,exist_ok=False)
 rows=json.loads(Path(a.roster).read_text()); assert [r['id'] for r in rows]==C.LANES+C.BASES
 assert all(r['status']=='available' for r in rows), 'provide actual complete evidence first'
 rt=ROOT/'runtime-environment.json'; image=json.loads(rt.read_text())['image']; entry=ROOT/'rc1_trackk.py'; source={p:C.sha(p) for p in sorted(C.required_sources())}
 host={'entry':str(entry),'state_dir':str(camp/'state'),'allocation':'/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json','owner':'rc1-trackk','dependency_policy':'wait-for-verified-free-resource','cpu_python':str(ROOT)+'-cpu/bin/python','cpu_environment':{'PATH':'/usr/bin:/bin','PYTHONPATH':str(ROOT),'PYTHONNOUSERSITE':'1'},'cpu_requires_numpy':True,'runtime_evidence':pin(rt),'matched_protocol':pin(ROOT/'experiments/RC1-MATCHED-K0.md'),'implementation_files':{str(p):C.sha(p) for p in [ROOT/'supervisor.py',*(ROOT/'tools'/n for n in ('r3_final_container.py','r3_resource_adapter.py','unified_resource_provider_v1.py','experiment_dag.py','unified_container_host_v1.py','unified_resource_lease_v1.py'))]},'r0_source_files':{str(p):C.sha(p) for p in sorted(H.R0.glob('*.py'))}}
 shared={'schema':'rc1-trackk-v1','protocol':pin(ROOT/'experiments/RC1-FUNCTIONAL-TEST.md'),'manifest':pin(Path(C.C.KEV_DIR)/'manifest.json'),'source_files':source,'image':image,'roster':rows,'round_dir':str(camp/'round'),'host':host}
 for row in rows:
  member=row['id']; out=camp/'runs'/member; final=camp/'configs'/(member+'.json'); review=camp/'reviews'/(member+'.json'); trans=camp/'transactions'/member
  mounts={x:False for x in [*source,str(ROOT/'runtime-environment.json'),host['matched_protocol']['path'],shared['protocol']['path'],shared['manifest']['path'],str(final),str(review),str(H.CLOSURE),str(H.R0)]}
  for s,p,suf in [('decision-v7','train',''),('decision-v7','calibration',''),('decision-v7','test',''),('decision-v7','test','.variants'),('transfer-v4','test',''),('transfer-v4','test','.variants')]: mounts[str(Path(C.C.KEV_DIR)/s/(p+suf+'.jsonl'))]=False
  for r in rows:
   for x in [r['model'],r.get('adapter'),*[v['path'] for v in r['evidence'].values()]]:
    if x: mounts[x]=False
  mounts.update({str(out):True,str(camp/'round'):True})
  spec={'name':'rc1-test-'+member,'image':image,'cmd':[],'mounts':mounts,'devices':['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(a.chip)],'environment':{}}
  c={**shared,'member':member,'out':str(out),'container':{'spec':spec,'run':'rc1-'+member,'chip':a.chip,'claim':str(trans/'claim.json'),'release':str(trans/'release.json'),'launch_receipt':str(trans/'launch.json')}}
  path=camp/'drafts'/(member+'.input.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(c,indent=2)+'\n')
  subprocess.run([sys.executable,'-P',str(ROOT/'config_builder.py'),'--template',str(path),'--runtime',str(rt),'--entry',str(entry),'--config-path',str(final),'--output',str(camp/'drafts'/(member+'.json'))],check=True)
 print(json.dumps({'campaign':str(camp),'drafts':12,'status':'unreviewed','review_paths_are_future':True}))
if __name__=='__main__':main()
