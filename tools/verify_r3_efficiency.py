#!/usr/bin/env python3
"""CPU-only acceptance check for the R3 efficiency window.

This never reads a test split and never changes resource ownership. It accepts only a natural
trainer terminal marker, a complete manifest and a measured post-warmup window.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re
from pathlib import Path

def sha(path):
 h=hashlib.sha256();
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1<<20), b''): h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',required=True); ap.add_argument('--plan',required=True); ap.add_argument('--warmup-steps',type=int,default=5); ap.add_argument('--min-measured-steps',type=int,default=10); ap.add_argument('--min-wall-seconds',type=float,default=60.0); ap.add_argument('--output', required=True); a=ap.parse_args()
 run=Path(a.run); plan=json.loads(Path(a.plan).read_text());
 if plan.get('out') != str(run): raise SystemExit('plan output mismatch')
 done=run/'DONE'; failed=run/'FAILED'
 if failed.exists() or not done.exists(): raise SystemExit('terminal marker is not successful DONE')
 marker=done.read_text();
 if not re.search(r'(?:^|\s)rc=0(?:\s|$)', marker): raise SystemExit('DONE marker is not rc=0')
 manifest=json.loads((run/'manifest.json').read_text())
 if manifest.get('arm') != 'k1' or manifest.get('args',{}).get('seed') != 2: raise SystemExit('manifest identity mismatch')
 rows=[]
 with (run/'losses.jsonl').open() as f:
  for line in f:
   if line.strip(): rows.append(json.loads(line))
 if len(rows) < a.warmup_steps+a.min_measured_steps: raise SystemExit(f'only {len(rows)} loss rows')
 command=plan['command']
 total=int(command[command.index('--total-steps')+1])
 if total <= 0 or len(rows) != total or [x.get('step') for x in rows] != list(range(1,total+1)): raise SystemExit('incomplete or noncontiguous steps')
 if manifest.get('summary',{}).get('final_step') != total or manifest.get('total_steps') != total: raise SystemExit('manifest step mismatch')
 if a.warmup_steps < 0 or a.min_measured_steps < 10 or a.min_wall_seconds < 60: raise SystemExit('invalid measurement thresholds')
 for row in rows:
  if any(not math.isfinite(float(row[k])) for k in ('loss','step_s','tok_s_chip','q_s_chip','tokens','base_questions')): raise SystemExit('nonfinite measurement')
  if any(float(row[k]) <= 0 for k in ('step_s','tokens','base_questions','tok_s_chip','q_s_chip')): raise SystemExit('nonpositive measurement')
 for name,digest in manifest['code_sha256'].items():
  source=Path(plan['code_dir'])/name
  if sha(source)!=digest or plan['files'].get(str(source))!=digest: raise SystemExit('training source hash mismatch')
 if manifest['train_file']['sha256']!=plan['files'].get(manifest['train_file']['path']): raise SystemExit('train identity mismatch')
 measured=rows[a.warmup_steps:]
 wall=sum(float(x['step_s']) for x in measured)
 if wall < a.min_wall_seconds: raise SystemExit(f'measured wall {wall:.3f}s < {a.min_wall_seconds:.3f}s')
 if any(float(x.get('tok_s_chip',0)) <= 0 or float(x.get('q_s_chip',0)) <= 0 for x in measured): raise SystemExit('non-positive throughput')
 progress=(run/'progress.log').read_text().splitlines()
 mem=[]
 for line in progress:
  match=re.search(r'\breserved_gib(?:=|\s+)(\S+)',line)
  if match: mem.append(float(match.group(1)))
 if not mem or any(not math.isfinite(x) or x<=0 for x in mem): raise SystemExit('reserved memory not recorded or invalid')
 peak=float(manifest['summary']['peak_reserved_gib'])
 if not math.isfinite(peak) or peak<=0 or abs(max(mem)-peak)>0.11: raise SystemExit('memory summary mismatch')
 result={'schema':'r3-efficiency-acceptance-v1','plan_sha256':sha(a.plan),'run':str(run),'terminal_marker_sha256':sha(done),'manifest_sha256':sha(run/'manifest.json'),'warmup_steps':a.warmup_steps,'measured_steps':len(measured),'measured_wall_seconds':wall,'mean_tok_s_chip':sum(float(x['tok_s_chip']) for x in measured)/len(measured),'mean_q_s_chip':sum(float(x['q_s_chip']) for x in measured)/len(measured),'reserved_gib_max':max(mem),'scientific_acceptance':False,'test_read':False,'status':'ENGINEERING_REVERIFIED', 'tokens_per_second_per_chip':sum(float(x['tokens']) for x in measured)/wall, 'questions_per_second_per_chip':sum(float(x['base_questions']) for x in measured)/wall, 'peak_reserved_gib_exact':peak, 'chips':1, 'verifier_sha256':sha(__file__), 'limitations':['Post-hoc all-postwarmup window; original frozen ten-step acceptance did not pass.', 'CPU recomputation only; not independent Astra approval or formal scientific acceptance.']}
 with Path(a.output).open('x') as f: f.write(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
 print(json.dumps(result,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
