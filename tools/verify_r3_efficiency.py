#!/usr/bin/env python3
"""CPU-only acceptance check for the R3 efficiency window.

This never reads a test split and never changes resource ownership. It accepts only a natural
trainer terminal marker, a complete manifest and a measured post-warmup window.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(path):
 h=hashlib.sha256();
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1<<20), b''): h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',required=True); ap.add_argument('--plan',required=True); ap.add_argument('--warmup-steps',type=int,default=5); ap.add_argument('--min-measured-steps',type=int,default=10); ap.add_argument('--min-wall-seconds',type=float,default=60.0); a=ap.parse_args()
 run=Path(a.run); plan=json.loads(Path(a.plan).read_text());
 if plan.get('out') != str(run): raise SystemExit('plan output mismatch')
 done=run/'DONE'; failed=run/'FAILED'
 if failed.exists() or not done.exists(): raise SystemExit('terminal marker is not successful DONE')
 marker=done.read_text();
 if 'rc=0' not in marker: raise SystemExit('DONE marker is not rc=0')
 manifest=json.loads((run/'manifest.json').read_text())
 if manifest.get('arm') != 'k1' or manifest.get('args',{}).get('seed') != 2: raise SystemExit('manifest identity mismatch')
 rows=[]
 with (run/'losses.jsonl').open() as f:
  for line in f:
   if line.strip(): rows.append(json.loads(line))
 if len(rows) < a.warmup_steps+a.min_measured_steps: raise SystemExit(f'only {len(rows)} loss rows')
 measured=rows[a.warmup_steps:a.warmup_steps+a.min_measured_steps]
 wall=sum(float(x['step_s']) for x in measured)
 if wall < a.min_wall_seconds: raise SystemExit(f'measured wall {wall:.3f}s < {a.min_wall_seconds:.3f}s')
 if any(float(x.get('tok_s_chip',0)) <= 0 or float(x.get('q_s_chip',0)) <= 0 for x in measured): raise SystemExit('non-positive throughput')
 progress=(run/'progress.log').read_text().splitlines()
 mem=[]
 for line in progress:
  for token in line.split():
   if token.startswith('reserved_gib='):
    try: mem.append(float(token.split('=',1)[1]))
    except ValueError: pass
 if not mem: raise SystemExit('reserved memory not recorded')
 result={'schema':'r3-efficiency-acceptance-v1','plan_sha256':sha(a.plan),'run':str(run),'terminal_marker_sha256':sha(done),'manifest_sha256':sha(run/'manifest.json'),'warmup_steps':a.warmup_steps,'measured_steps':len(measured),'measured_wall_seconds':wall,'mean_tok_s_chip':sum(float(x['tok_s_chip']) for x in measured)/len(measured),'mean_q_s_chip':sum(float(x['q_s_chip']) for x in measured)/len(measured),'reserved_gib_max':max(mem),'scientific_acceptance':False,'test_read':False,'status':'ENGINEERING_ACCEPTED'}
 (run/'EFFICIENCY_ACCEPTED.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps(result,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
