#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import sys; sys.path.insert(0,str(Path(__file__).resolve().parent))
import core
from transformers import AutoTokenizer
p=argparse.ArgumentParser(); p.add_argument('--mask',required=True); p.add_argument('--dev-root',required=True); p.add_argument('--model',required=True); p.add_argument('--out',required=True); a=p.parse_args()
raw=Path(a.mask).read_bytes()
if core.digest_bytes(raw)!='df9da52a09bed12d562aad304d59863f9c90cc7a46c27b87c818a580774db03d': raise ValueError('mask hash mismatch')
rows=core.read_dev(json.loads(raw),a.dev_root); tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,trust_remote_code=False)
longest=None
for key,items in rows.items():
    for i,row in enumerate(items):
        _,pre,cands=core.encode(row,tok); length=len(pre)+max(map(len,cands))
        x=(length,key,i)
        if longest is None or x>longest: longest=x
chosen={(key,0) for key in rows}; chosen.add((longest[1],longest[2]))
work=[]
for key,i in sorted(chosen):
    row=rows[key][i]; _,pre,c=core.encode(row,tok)
    work.append(dict(source_key=key,row=i,row_sha256=core.digest(row),prefix_length=len(pre),candidate_lengths=list(map(len,c))))
core.put(a.out,dict(schema='qwen38-dev-smoke-v1',selection='row 0 of each DEV file plus longest full sequence by token count; ties lexicographic key/index',mask_sha256=core.digest_bytes(raw),model='Qwen/Qwen3.8-27B',revision='1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0',longest=list(longest),modes=['full','blank','drop'],items=work))
print('frozen',len(work),'items; longest',longest,flush=True)
