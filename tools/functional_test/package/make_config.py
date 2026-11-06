#!/usr/bin/env python3
"""Create collector mapping from the assembled campaign; never access dataset payloads."""
import argparse, ast, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import collector as C

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--campaign',required=True);p.add_argument('--producer',required=True);p.add_argument('--wrapper',required=True)
 p.add_argument('--consumer',required=True);p.add_argument('--source-acceptance',required=True);p.add_argument('--completed-access-review',required=True)
 p.add_argument('--module-dir',action='append',required=True);p.add_argument('--output',required=True)
 p.add_argument('--reference-metadata');p.add_argument('--reference-performance-export');p.add_argument('--workers',type=int,default=2)
 a=p.parse_args();root=Path(a.campaign).resolve();producer=Path(a.producer).resolve();consumer=Path(a.consumer).resolve()
 if C.sha(producer)!='cf5a82bd77d4f4f047f80d228ebf55ae96148d19accbc5ce7d0cf6db95543e1f':raise ValueError('producer bytes differ')
 if C.sha(consumer)!='0175b541393104297295fe6ad36bfcbba61509fc80c6b186b251af8f2400dde6':raise ValueError('consumer bytes differ')
 tree=ast.parse(producer.read_text());data=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DATA' for x in n.targets))
 cfg={'kind':'production','configs':{r:str(root/'configs'/(r+'.json')) for r in C.ROLES},'export_dir':str(root/'population-export'),'export_member':'q0p8b-s2','identity_cache':str(root/'round/.model_hash_cache.json'),'producer':str(producer),'bootstrap_wrapper':str(Path(a.wrapper).resolve()),'consumer':str(consumer),'consumer_sha256':C.sha(consumer),'module_dirs':[str(Path(x).resolve()) for x in a.module_dir],'data_pins':{'/'.join(k):{'n':v[0],'sha256':v[1]} for k,v in data.items()},'source_acceptance':C.pin(a.source_acceptance),'completed_access_review':str(Path(a.completed_access_review).resolve()),'workers':a.workers}
 for arg,key in ((a.reference_metadata,'reference_metadata'),(a.reference_performance_export,'reference_performance_export')):
  if arg:cfg[key]=C.pin(arg)
 if not 1<=a.workers<=8:raise ValueError('workers must be 1..8')
 C.save(a.output,cfg)
if __name__=='__main__':main()
