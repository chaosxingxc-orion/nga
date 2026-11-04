"""Validate imported checkpoint at container startup, then invoke original driver."""
import hashlib,json,os,sys,runpy
from pathlib import Path

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def validate(p):
 root=Path(p['out']);r=p['recovery']
 if sorted(x.name for x in (root/'ckpt').iterdir())!=['step_002400.pt']:raise RuntimeError('startup checkpoint inventory differs')
 if digest(root/'ckpt/step_002400.pt')!=r['checkpoint']['sha256'] or digest(root/'losses.jsonl')!=r['loss_prefix']['sha256']:raise RuntimeError('startup imports differ')
 origin=Path(__file__).with_name('r3_original_formal_driver.py')
 if digest(origin)!=p['files'][str(Path(p['code'])/'r3_original_formal_driver.py')]:raise RuntimeError('original driver changed')
 return origin
if __name__=='__main__':
 plan=Path(sys.argv[sys.argv.index('--plan')+1]);p=json.loads(plan.read_text());root=Path(p['out']);attempt=int(sys.argv[sys.argv.index('--attempt')+1]);a=root/'attempts'/str(attempt)
 try:origin=validate(p)
 except BaseException as error:
  a.mkdir(parents=True,exist_ok=True);v={'exit_code':125,'attempt':attempt,'source':'recovery-import-validation','error':str(error),'scientific_acceptance':False}
  for target in [a/'EXIT.json',root/'TRAIN_EXIT.json']:
   tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(v)+'\n');os.replace(tmp,target)
  raise
 runpy.run_path(str(origin),run_name='__main__')
