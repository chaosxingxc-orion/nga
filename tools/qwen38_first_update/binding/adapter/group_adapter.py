#!/usr/bin/env python3
"""Atomic group ledger transactions; requires a reviewed controller before use."""
import argparse, importlib.util, json, sys
from pathlib import Path

spec=importlib.util.spec_from_file_location('r3',str(Path(__file__).with_name('r3_resource_adapter.py')))
r3=importlib.util.module_from_spec(spec); spec.loader.exec_module(r3)

def transact(op, alloc, chips, run, proof, claim_path=None, container=None, container_id=None, claim_guard=None, absent=False, purpose='engineering forward'):
    if not isinstance(purpose,str) or not purpose.strip(): raise ValueError('nonempty purpose required')
    chips=sorted(chips); proof=Path(proof); intent=Path(str(proof)+'.intent')
    if len(chips) not in (2,4) or len(set(chips)) != len(chips) or any(type(c)!=int or not 0<=c<8 for c in chips): raise ValueError('invalid group')
    alloc=r3.validated_path(alloc)
    claim=None; claim_hash=None
    if op=='release':
        raw=r3.read_bytes(claim_path); claim=json.loads(raw); claim_hash=r3.sha_bytes(raw)
        if claim.get('op')!='claim' or claim.get('run')!=run or claim.get('chips')!=chips or claim.get('allocation')!=str(alloc): raise RuntimeError('claim identity differs')
        if not container_id and not absent: raise RuntimeError('retained container ID required')
    def physical():
        if op=='claim':
            if any(r3.live_chip_conflict(c,None) for c in chips): raise RuntimeError('physical conflict')
        else:
            if r3.sha_bytes(r3.read_bytes(claim_path))!=claim_hash: raise RuntimeError('claim changed')
            obj=r3.docker_inspect(container)
            if absent:
                if obj is not None: raise RuntimeError('container absence not confirmed')
            elif obj is None or obj['Id']!=container_id or obj['State'].get('Status') not in ('exited','dead') or obj['HostConfig'].get('AutoRemove'): raise RuntimeError('retained container identity or state differs')
            bound=sorted(int(x['PathOnHost'].removeprefix('/dev/davinci')) for x in (obj['HostConfig'].get('Devices',[]) if obj else []) if x['PathOnHost'].startswith('/dev/davinci') and x['PathOnHost'].removeprefix('/dev/davinci').isdigit())
            if not absent and bound!=chips: raise RuntimeError('container device bindings differ')
            if any(r3.live_chip_conflict(c,None) for c in chips): raise RuntimeError('physical conflict')
    proof.parent.mkdir(parents=True,exist_ok=True)
    with r3.locked(alloc):
        raw=r3.read_bytes(alloc); doc=json.loads(raw); r3.validate_doc(doc)
        if op == 'claim' and claim_guard is not None: claim_guard(doc)
        if proof.exists(): raise RuntimeError('proof exists; inspect before retry')
        if intent.exists():
            it=r3.load(intent)
            if (it['op'],it['run'],it['chips'],it['allocation'],it.get('claim_sha256'),it.get('container_id'),it.get('absent',False))!=(op,run,chips,str(alloc),claim_hash,container_id,absent): raise RuntimeError('intent identity differs')
            if op=='claim' and it.get('purpose','engineering forward') != purpose: raise RuntimeError('intent purpose differs')
            h=r3.sha_bytes(raw)
            if h==it['before_sha256']:
                physical(); r3.write_atomic(alloc,it['after'])
            elif h!=it['after_sha256']: raise RuntimeError('ledger diverged; explicit reconciliation required')
            r3.write_atomic(proof,it); intent.unlink(); return
        physical()
        after=dict(doc); now=r3.utc()
        if op=='claim':
            if any(sum(e['chip']==c for e in doc['free'])!=1 for c in chips): raise RuntimeError('group unavailable')
            entries=[dict(chip=c,run=run,owner='qwen38 admission',purpose=purpose,claimed_utc=now,claim_evidence=str(proof.resolve()),release_when='retained container exited and group released') for c in chips]
            after['free']=[e for e in doc['free'] if e['chip'] not in chips]; after['allocation']=sorted(doc['allocation']+entries,key=lambda x:x['chip'])
        elif op=='release':
            entries=claim['entries']
            if sorted([e for e in doc['allocation'] if e['chip'] in chips],key=lambda x:x['chip'])!=entries or any(e['chip'] in chips for e in doc['free']): raise RuntimeError('ownership generation differs')
            after['allocation']=[e for e in doc['allocation'] if e['chip'] not in chips]; after['free']=sorted(doc['free']+[dict(chip=c,previous_run=run,release_evidence=str(proof.resolve()),released_utc=now) for c in chips],key=lambda x:x['chip'])
        else: raise ValueError('invalid operation')
        after['updated_utc']=now; after['updated_by']='qwen38 group adapter '+op
        encoded=(json.dumps(after,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
        it=dict(schema='qwen38-group-transaction-v1',op=op,run=run,chips=chips,allocation=str(alloc),entries=entries,before_sha256=r3.sha_bytes(raw),after_sha256=r3.sha_bytes(encoded),after=after,claim_sha256=claim_hash,container=container,container_id=container_id,absent=absent,utc=now)
        if op=='claim': it['purpose']=purpose
        r3.write_atomic(intent,it); physical()
        if r3.read_bytes(alloc)!=raw: raise RuntimeError('ledger changed')
        r3.write_atomic(alloc,after); r3.write_atomic(proof,it); intent.unlink()

def main():
    p=argparse.ArgumentParser(); p.add_argument('op',choices=['claim','release']); p.add_argument('--alloc',required=True); p.add_argument('--chips',type=int,nargs='+',required=True); p.add_argument('--run',required=True); p.add_argument('--proof',required=True); p.add_argument('--claim'); p.add_argument('--container'); p.add_argument('--container-id'); a=p.parse_args()
    transact(a.op,a.alloc,a.chips,a.run,a.proof,a.claim,a.container,a.container_id)
if __name__=='__main__': main()
