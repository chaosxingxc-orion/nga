#!/usr/bin/env python3
"""Recompute one candidate from saved NPU logits on CPU, after release."""
import argparse, hashlib, json, math
from pathlib import Path
import torch

def evaluate(ref):
 ref=Path(ref); m=json.loads((ref/'manifest.json').read_text()); data=(ref/'logits.pt').read_bytes()
 if hashlib.sha256(data).hexdigest()!=m['logits_sha256']: raise ValueError('logits checksum mismatch')
 logits=torch.load(ref/'logits.pt',map_location='cpu',weights_only=True)
 ids=m['candidate_token_ids']; n=len(ids)
 if n<2 or list(logits.shape)!=m['shape'] or logits.shape[0]!=n+1 or logits.dtype!=torch.float32: raise ValueError('reference shape/dtype mismatch')
 lp=torch.log_softmax(logits,dim=-1)
 score=sum(float(lp[i,token]) for i,token in enumerate(ids)); original=m['npu_score']; diff=abs(score-original)
 return {'cpu_score':score,'npu_score':original,'absolute_difference':diff,'relative_difference':diff/max(abs(original),1e-30),'absolute_tolerance':m['absolute_tolerance'],'relative_tolerance':m['relative_tolerance'],'pass':math.isclose(score,original,abs_tol=m['absolute_tolerance'],rel_tol=m['relative_tolerance']),'scope':'same NPU-produced logits, CPU reduction only; no independent model forward','logits_sha256':m['logits_sha256']}
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('reference'); p.add_argument('--release',required=True); a=p.parse_args()
 proof=json.loads(Path(a.release).read_text())
 if proof.get('op')!='release': raise SystemExit('release proof required before CPU reconstruction')
 result=evaluate(a.reference); dest=Path(a.reference)/'cpu-result.json'; dest.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result)); raise SystemExit(0 if result['pass'] else 1)
