"""Fixed CPU-only JSON/NPY serialization and bounded threaded readout benchmark."""
import argparse, concurrent.futures, json, os, tempfile, time
from pathlib import Path
import numpy as np

def bench(root,n,workers):
 root=Path(root); rng=np.random.default_rng(20261105); vectors=[rng.standard_normal(248320,dtype=np.float32) for _ in range(n)]
 vectors[0][:4]=np.array([-0.,0.,np.finfo(np.float32).tiny,np.nextafter(np.float32(0),np.float32(1))],dtype=np.float32)
 results={}
 with tempfile.TemporaryDirectory(prefix='nga-io-bench-',dir=root) as tmp:
  d=Path(tmp)
  for fmt in ('json','npy'):
   t=time.perf_counter()
   for i,z in enumerate(vectors):
    with (d/f'{fmt}{i}').open('wb') as f:
     if fmt=='json': f.write(json.dumps(z.tolist(),allow_nan=False,separators=(',',':')).encode())
     else: np.save(f,z,allow_pickle=False)
     f.flush();os.fsync(f.fileno())
   write=time.perf_counter()-t; size=sum((d/f'{fmt}{i}').stat().st_size for i in range(n))
   def read(i):
    with (d/f'{fmt}{i}').open('rb') as f:
     z=np.asarray(json.load(f),dtype=np.float32) if fmt=='json' else np.load(f,allow_pickle=False)
    if not np.array_equal(z.view('u4'),vectors[i].view('u4')): raise ValueError('bits differ')
    # Same candidate-restricted float64 arithmetic used by the native readout.
    x=z[[1,2,3]].astype(np.float64); a=x.max(); return x-(a+np.log(np.exp(x-a).sum()))
   t=time.perf_counter()
   with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool: scores=list(pool.map(read,range(n)))
   results[fmt]={'write_fsync_seconds':write,'read_score_seconds':time.perf_counter()-t,'bytes':size,'scores':[v.tolist() for v in scores]}
 if results['json'].pop('scores')!=results['npy'].pop('scores'): raise ValueError('scores differ')
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--count',type=int,default=8);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
 if not 1<=a.count<=32 or not 1<=a.workers<=4: raise ValueError('bounded fixture only')
 print(json.dumps({'root':a.root,'count':a.count,'workers':a.workers,'results':bench(a.root,a.count,a.workers)},indent=2))
