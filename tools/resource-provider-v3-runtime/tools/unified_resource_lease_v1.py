#!/usr/bin/env python3
"""Locked, journalled physical leases. Scientific admission is a separate concern.

Config is JSON data, never Python. See validate_config for its exact v1 shape.
Docker query implements inspect(name) and conflict(chip), with uncertain observations
raising exceptions. All allocation and dispatch-policy writers must cooperate on
allocation+'.lock'; use update_dispatch_policy for policy changes. The accepted
policy pin is immutable; optional dispatch_policy is a separate mutable path.
Legacy configs use the pinned policy itself as the dispatch snapshot.

The ledger write is the transaction linearization point. An intent with the
before-image has not committed and a claim requires dispatch permission again;
an intent with the after-image has committed and may be published under HOLD.
Receipt publication does not grant start/bind authority. A crash after a ledger
write can leave an intent without a receipt; a divergent ledger requires manual
reconciliation. Policy snapshots and ledger writes are serialized only among
cooperating writers. Pin and dispatch rechecks detect changes before commit,
but do not provide a malicious-filesystem or post-check race guarantee.

"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

try:
    from . import r3_resource_adapter as R
except ImportError:
    import r3_resource_adapter as R


def need(ok, message):
    if not ok: raise ValueError(message)

def digest(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()).hexdigest()

def ref(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256'}, 'invalid pinned reference')
    need(type(ref['path']) is str and os.path.isabs(ref['path']) and isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256']), 'invalid reference')
    raw=R.read_bytes(ref['path']); need(R.sha_bytes(raw)==ref['sha256'], 'pinned file changed')
    return json.loads(raw)

def validate_config(c):
    need(type(c) is dict, 'config fields')
    fields=set(c)-{'dispatch_policy'}
    need(fields in ({'schema','allocation','journal','lease_id','owner','run','task_sha256','eligible_device_ids','device_count','priority','priority_override','policy','acceptance','predecessors'}, {'schema','allocation','journal','lease_id','owner','run','task_sha256','eligible_device_ids','device_count','priority','priority_override','policy','acceptance','evidence_roots'}), 'config fields')
    need(c['schema']=='unified-resource-lease-config-v1', 'config schema')
    for k in ('allocation','journal'):
        need(type(c[k]) is str and os.path.isabs(c[k]) and os.path.normpath(c[k])==c[k], 'absolute normalized path required')
    for k in ('lease_id','owner','run'):
        need(type(c[k]) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',c[k]) and c[k] not in ('.','..'), 'invalid identity')
    need(type(c['task_sha256']) is str and re.fullmatch('[0-9a-f]{64}',c['task_sha256']), 'task digest')
    ids=c['eligible_device_ids']; need(type(ids) is list and ids==sorted(set(ids)) and all(type(x) is int and 0<=x<8 for x in ids), 'eligible devices')
    need(type(c['device_count']) is int and c['device_count'] in (1,2,4) and len(ids)>=c['device_count'], 'device count')
    need(type(c['priority']) is int and 0<=c['priority']<=100, 'priority')
    need(c['priority_override'] is None or type(c['priority_override']) is dict, 'priority override')
    for k in ('policy','acceptance'): ref(c[k])
    if 'dispatch_policy' in c:
        p=c['dispatch_policy']; need(type(p) is str and os.path.isabs(p) and os.path.normpath(p)==p and p not in (c['policy']['path'],c['acceptance']['path'],c['allocation']) and os.path.commonpath((c['journal'],p))!=c['journal'], 'dispatch policy path')
    need(type(c.get('predecessors', {})) is dict and all(type(k) is str and k in [str(x) for x in ids] for k in c.get('predecessors', {})), 'predecessors')
    for v in c.get('predecessors', {}).values():
        need(type(v) is dict and set(v)=={'claim','release','container','terminal'}, 'predecessor references')
        for p in v.values():
            if p is not None: ref(p)
    if 'evidence_roots' in c:
        need(type(c['evidence_roots']) is list and bool(c['evidence_roots']) and all(type(x) is str and os.path.isabs(x) and os.path.normpath(x)==x for x in c['evidence_roots']), 'evidence roots')
    if c['priority_override'] is not None: ref(c['priority_override'])
    return c

def accepted_identity(c):
    policy=ref(c['policy']); acceptance=ref(c['acceptance'])
    need(policy.get('schema')=='nga-engineering-release-policy-v1', 'accepted policy schema')
    need(acceptance.get('schema')=='unified-resource-acceptance-v1' and acceptance.get('decision')=='accept' and acceptance.get('policy_sha256')==c['policy']['sha256'] and acceptance.get('config_sha256')==config_hash(c), 'pinned acceptance differs')
    return policy

def dispatch_snapshot(c):
    policy=accepted_identity(c)
    if 'dispatch_policy' in c:
        raw=R.read_bytes(c['dispatch_policy']); policy=json.loads(raw)
    else:
        raw=R.read_bytes(c['policy']['path'])
        need(R.sha_bytes(raw)==c['policy']['sha256'], 'pinned file changed')
    need(policy.get('schema')=='nga-engineering-release-policy-v1' and policy.get('new_experiment_dispatch')=='allow', 'dispatch policy HOLD')
    return raw

def authority_files(c):
    # Detect atomic pin replacement even when the replacement has identical bytes.
    paths=[c['policy']['path'],c['acceptance']['path']]
    if 'dispatch_policy' in c: paths.append(c['dispatch_policy'])
    return tuple((os.stat(p).st_dev,os.stat(p).st_ino,os.stat(p).st_mtime_ns,os.stat(p).st_size) for p in paths)

def update_dispatch_policy(c, policy):
    # All dispatch writers must use this lock, including writers setting HOLD.
    alloc=locked_config(c); need('dispatch_policy' in c, 'separate dispatch policy required')
    need(type(policy) is dict and policy.get('schema')=='nga-engineering-release-policy-v1' and policy.get('new_experiment_dispatch') in ('allow','hold'), 'invalid dispatch policy')
    with R.locked(alloc):
        accepted_identity(c)
        R.read_bytes(c['dispatch_policy'])  # existing regular file, no symlink components
        R.write_atomic(c['dispatch_policy'],policy)

def authorize(c):
    return dispatch_snapshot(c)

def config_hash(c):
    # Acceptance cannot contain its own hash.
    return digest({k:v for k,v in c.items() if k!='acceptance'})

class DockerQuery:
    def inspect(self,name): return R.docker_inspect(name)
    def conflict(self,chip): return R.live_chip_conflict(chip,None)

def devices(obj):
    host=obj.get('HostConfig'); need(type(host) is dict and host.get('AutoRemove') is False, 'container retention')
    ds=host.get('Devices'); need(type(ds) is list, 'device list missing')
    out=[]
    for x in ds:
        need(type(x) is dict and type(x.get('PathOnHost')) is str, 'invalid device')
        m=re.fullmatch(r'/dev/davinci([0-7])',x['PathOnHost'])
        if m:
            need(x.get('PathInContainer')==x['PathOnHost'], 'device mapping differs'); out.append(int(m[1]))
    need(len(out)==len(set(out)), 'ambiguous device mapping')
    return sorted(out)

def retained(q,name,ident, chips, exit_code=None, started=None, finished=None):
    obj=q.inspect(name); need(type(obj) is dict and type(ident) is str and obj.get('Id')==ident and len(ident)>=12, 'container generation differs')
    state=obj.get('State'); need(type(state) is dict and obj.get('RestartCount')==0, 'container generation ambiguous')
    need(devices(obj)==sorted(chips), 'container devices differ')
    if exit_code is not None:
        need(state.get('Status')=='exited' and state.get('Running') is False and type(state.get('ExitCode')) is int and state['ExitCode']==exit_code, 'container not physically exited')
        need(type(state.get('StartedAt')) is str and bool(state['StartedAt']) and type(state.get('FinishedAt')) is str and bool(state['FinishedAt']), 'missing generation timestamps')
        if started is not None: need(state['StartedAt']==started and state['FinishedAt']==finished, 'container timestamps differ')
    return obj

def evidence_refs(c, entry):
    path=entry.get('release_evidence')
    need(type(path) is str and os.path.isabs(path) and os.path.normpath(path)==path, 'invalid release path')
    roots=c.get('evidence_roots')
    if roots is None:
        return c['predecessors'].get(str(entry['chip']))
    need(any(os.path.commonpath((root,path))==root and path!=root for root in roots), 'release outside evidence roots')
    def pin(p):
        raw=R.read_bytes(p)
        return {'path':str(p),'sha256':R.sha_bytes(raw)}
    rr=pin(path); rel=ref(rr)
    registry={'unified-resource-transaction-v1':('claim.json',None,None),
              'r3-resource-release-v1':('CLAIM.json',None,None),
              'qwen38-group-transaction-v1':('CLAIM.json','CONTAINER.json','TERMINAL.json')}
    need(rel.get('schema') in registry, 'unsupported predecessor schema')
    names=registry[rel['schema']]; parent=Path(path).parent
    return dict(release=rr,claim=pin(parent/names[0]),container=pin(parent/names[1]) if names[1] else None,terminal=pin(parent/names[2]) if names[2] else None)

def predecessor(c, entry, q, refs=None):
    chip=entry['chip']; refs=refs or evidence_refs(c,entry); need(refs is not None, 'predecessor evidence required')
    cr,rr=refs['claim'],refs['release']; need(cr and rr and rr['path']==entry.get('release_evidence'), 'release reference differs')
    claim=ref(cr); rel=ref(rr); run=entry.get('previous_run'); need(type(run) is str and run, 'previous run required')
    need(str(Path(rr['path']).with_name('claim.json' if rel.get('schema')=='unified-resource-transaction-v1' else 'CLAIM.json'))==cr['path'], 'claim sibling differs')
    group=rel.get('schema')=='qwen38-group-transaction-v1'
    if rel.get('schema')=='unified-resource-transaction-v1':
        need(claim.get('schema')==rel['schema'] and claim.get('op')=='claim' and rel.get('op')=='release' and claim.get('config_sha256')==rel.get('config_sha256') and claim.get('allocation')==rel.get('allocation')==c['allocation'] and claim.get('chips')==rel.get('chips') and claim.get('entries')==rel.get('entries') and chip in rel['chips'] and all(x.get('run')==run for x in rel['entries']), 'unified lineage')
        for item in (claim,rel):
            R.validate_doc(item['before']); R.validate_doc(item['after'])
            need(digest(item['before'])==item.get('before_semantic_sha256',item['before_sha256']) and digest(item['after'])==item['after_sha256'], 'unified ledger hash')
        chips=rel['chips']; before=rel['before']; after=rel['after']; b=rel['binding']
        need([x for x in before['allocation'] if x['chip'] in chips]==rel['entries'] and after['allocation']==[x for x in before['allocation'] if x['chip'] not in chips] and [x for x in after['free'] if x['chip'] not in chips]==[x for x in before['free'] if x['chip'] not in chips] and all(before.get(k)==after.get(k) for k in set(before)|set(after) if k not in ('allocation','free','updated_utc','updated_by')), 'unified release transition')
        need(b['chips']==chips and b['config_sha256']==rel['config_sha256'] and type(rel['exit_code']) is int and rel['scientific_acceptance'] is False, 'unified binding')
        ob=retained(q,b['container'],b['container_id'],chips,rel['exit_code'],rel['started_at'],rel['finished_at'])
        labels=ob.get('Config',{}).get('Labels') or {}; need(labels.get('nga.lease_id')==b['lease_id'] and labels.get('nga.task_sha256')==b['task_sha256'], 'unified task binding')
    elif group:
        chips=rel.get('chips'); need(type(chips) is list and chips==sorted(set(chips)) and len(chips) in (2,4) and chip in chips and all(type(x) is int and 0<=x<8 for x in chips), 'group chips')
        need(claim.get('schema')==rel['schema'] and claim.get('op')=='claim' and rel.get('op')=='release' and claim.get('run')==rel.get('run')==run and claim.get('allocation')==rel.get('allocation')==c['allocation'] and claim.get('chips')==chips and rel.get('entries')==claim.get('entries') and rel.get('claim_sha256')==cr['sha256'] and rel.get('absent') is False, 'group lineage')
        for item in (claim,rel):
            R.validate_doc(item['after']); need(digest(item['after'])==item.get('after_sha256'), 'group ledger hash')
        need(all([x for x in claim['after']['allocation'] if x['chip']==i]==[x for x in claim['entries'] if x['chip']==i] for i in chips), 'group claim entries')
        need(all(not any(x['chip']==i for x in rel['after']['allocation']) and [x for x in rel['after']['free'] if x['chip']==i]==[dict(chip=i,previous_run=run,release_evidence=rr['path'],released_utc=rel['utc'])] for i in chips), 'group release entries')
        need(refs['container'] and refs['terminal'] and refs['container']['path']==str(Path(rr['path']).with_name('CONTAINER.json')) and refs['terminal']['path']==str(Path(rr['path']).with_name('TERMINAL.json')), 'group sibling references')
        container=ref(refs['container']); terminal=ref(refs['terminal']); code=terminal.get('exit_code')
        need(container.get('claim_sha256')==cr['sha256'] and container.get('id')==rel.get('container_id')==terminal.get('container_id') and container.get('config_sha256')==terminal.get('config_sha256') and type(code) is int, 'group container lineage')
        retained(q,rel['container'],rel['container_id'],chips,code)
        after=rel['after']
    else:
        need(rel.get('schema')=='r3-resource-release-v1' and claim.get('schema')=='r3-resource-claim-v1' and rel.get('run')==claim.get('run')==run and type(rel.get('chip')) is int and rel['chip']==claim.get('chip')==chip and claim.get('allocation')==c['allocation'] and rel.get('claim_sha256') in (None,cr['sha256']), 'single lineage')
        before=rel['allocation_before']; after=rel['allocation_after']
        for key,doc in (('allocation_before',before),('allocation_after',after)):
            R.validate_doc(doc); need(digest(doc)==rel.get(key+'_sha256'), 'single ledger hash')
        need([x for x in before['allocation'] if x['chip']==chip]==[claim.get('entry')] and not any(x['chip']==chip for x in before['free']), 'single ownership')
        need(after['allocation']==[x for x in before['allocation'] if x['chip']!=chip] and [x for x in after['free'] if x['chip']!=chip]==[x for x in before['free'] if x['chip']!=chip] and all(before.get(k)==after.get(k) for k in set(before)|set(after) if k not in ('allocation','free','updated_utc','updated_by')), 'single release transition')
        need(rel.get('scientific_acceptance') is False and type(rel.get('exit_code')) is int, 'single release scope')
        retained(q,rel['container'],rel['container_id'],[chip],rel['exit_code'],rel['container_started_at'],rel['container_finished_at'])
    need([x for x in after['free'] if x['chip']==chip]==[entry], 'free generation differs')
    need(not q.conflict(chip), 'live device conflict')

def paths(c,op):
    base=Path(c['journal'])/c['lease_id']; return base/(op+'.intent.json'),base/(op+'.json')

def locked_config(c):
    validate_config(c); accepted_identity(c)
    for p in (Path(c['journal']), Path(c['journal'])/c['lease_id']):
        need(not any(x.is_symlink() for x in (p,*p.parents)), 'symlink journal path')
    return R.validated_path(c['allocation'])

def transaction(c,op,build,check):
    alloc=locked_config(c); intent,receipt=paths(c,op)
    with R.locked(alloc):
        accepted_identity(c); pins=authority_files(c); raw=R.read_bytes(alloc); doc=json.loads(raw); R.validate_doc(doc)
        if receipt.exists():
            r=R.load(receipt); need(r.get('config_sha256')==config_hash(c) and r.get('op')==op, 'receipt identity differs')
            if op=='claim': need([x for x in doc['allocation'] if x['chip'] in r['chips']]==r['entries'], 'claim no longer owns generation')
            return r
        if intent.exists():
            it=R.load(intent); need(it.get('config_sha256')==config_hash(c) and it.get('op')==op and it.get('before_sha256') and digest(it['after'])==it.get('after_sha256'), 'intent identity differs')
            h=R.sha_bytes(raw)
            if h==it['before_sha256']:
                snapshot=authorize(c) if op=='claim' else None
                check(doc,it); need(R.read_bytes(alloc)==raw, 'ledger changed'); accepted_identity(c); need(authority_files(c)==pins, 'authority file replaced')
                if op=='claim': need(authorize(c)==snapshot, 'dispatch policy changed')
                R.write_atomic(alloc,it['after'])
            else: need(h==it['after_sha256'], 'ledger diverged; manual reconciliation required')
        else:
            snapshot=authorize(c) if op=='claim' else None
            after,extra=build(doc); check(doc,extra)
            it=dict(schema='unified-resource-transaction-v1',op=op,config_sha256=config_hash(c),allocation=c['allocation'],before_sha256=R.sha_bytes(raw),before_semantic_sha256=digest(doc),before=doc,after=after,after_sha256=digest(after),**extra)
            intent.parent.mkdir(parents=True,exist_ok=True); R.write_atomic(intent,it)
            check(doc,it); need(R.read_bytes(alloc)==raw, 'ledger changed'); accepted_identity(c); need(authority_files(c)==pins, 'authority file replaced')
            if op=='claim': need(authorize(c)==snapshot, 'dispatch policy changed')
            R.write_atomic(alloc,after)
        accepted_identity(c); R.write_atomic(receipt,it); intent.unlink(); return it

def claim(c,query):
    def build(doc):
        pending=doc.get('pending_claims'); need(pending is not None, 'pending claims snapshot missing')
        if pending:
            need(c['priority_override'] is not None, 'pending claims require explicit priority override')
            override=ref(c['priority_override']); need(override==dict(schema='unified-priority-override-v1',decision='authorize',allocation=c['allocation'],lease_id=c['lease_id'],priority=c['priority'],pending_sha256=digest(pending),task_sha256=c['task_sha256']), 'priority override differs')
        free={x['chip']:x for x in doc['free']}; chosen=[x for x in c['eligible_device_ids'] if x in free][:c['device_count']]
        need(len(chosen)==c['device_count'], 'insufficient eligible free devices')
        now=R.utc(); entries=[dict(chip=x,owner=c['owner'],run=c['run'],lease_id=c['lease_id'],task_sha256=c['task_sha256'],claimed_utc=now,claim_evidence=str(paths(c,'claim')[1])) for x in chosen]
        after=dict(doc,free=[x for x in doc['free'] if x['chip'] not in chosen],allocation=sorted(doc['allocation']+entries,key=lambda x:x['chip']),updated_utc=now,updated_by='unified resource claim')
        return after,dict(chips=chosen,entries=entries,free_entries=[free[x] for x in chosen],predecessor_evidence=[evidence_refs(c,free[x]) for x in chosen],pending_claims=pending)
    def check(doc,it):
        need(doc.get('pending_claims')==it['pending_claims'], 'pending claims changed')
        if it['pending_claims']:
            override=ref(c['priority_override']); need(override.get('pending_sha256')==digest(it['pending_claims']) and override.get('lease_id')==c['lease_id'] and override.get('task_sha256')==c['task_sha256'] and override.get('priority')==c['priority'] and override.get('allocation')==c['allocation'] and override.get('decision')=='authorize' and override.get('schema')=='unified-priority-override-v1', 'priority authority changed')
        for entry,refs in zip(it['free_entries'],it['predecessor_evidence']):
            need(entry in doc['free'] and evidence_refs(c,entry)==refs, 'free evidence changed'); predecessor(c,entry,query,refs)
    return transaction(c,'claim',build,check)

def bind_container(c,query,name,container_id):
    alloc=locked_config(c); need(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name) and type(container_id) is str and re.fullmatch('[0-9a-f]{64}',container_id), 'container identity')
    with R.locked(alloc):
        snapshot=authorize(c); pins=authority_files(c); claim_record=R.load(paths(c,'claim')[1]); need(claim_record.get('config_sha256')==config_hash(c), 'claim identity')
        doc=R.load(alloc); R.validate_doc(doc); need([x for x in doc['allocation'] if x['chip'] in claim_record['chips']]==claim_record['entries'], 'claim generation differs')
        obj=retained(query,name,container_id,claim_record['chips']); state=obj['State']; need(state.get('Status') in ('created','running','exited'), 'container state')
        labels=obj.get('Config',{}).get('Labels') or {}; need(labels.get('nga.lease_id')==c['lease_id'] and labels.get('nga.task_sha256')==c['task_sha256'], 'container task binding differs')
        binding=dict(schema='unified-resource-binding-v1',config_sha256=config_hash(c),lease_id=c['lease_id'],task_sha256=c['task_sha256'],chips=claim_record['chips'],container=name,container_id=container_id)
        path=paths(c,'binding')[1]
        if path.exists(): need(R.load(path)==binding, 'binding differs')
        else:
            need(authorize(c)==snapshot and authority_files(c)==pins, 'dispatch policy or pin changed'); R.write_atomic(path,binding)
        return binding

def release(c,query):
    def evidence():
        cl=R.load(paths(c,'claim')[1]); b=R.load(paths(c,'binding')[1]); need(cl.get('config_sha256')==b.get('config_sha256')==config_hash(c) and b.get('chips')==cl.get('chips') and b.get('lease_id')==c['lease_id'] and b.get('task_sha256')==c['task_sha256'], 'binding mismatch')
        obj=query.inspect(b['container']); need(type(obj) is dict and type(obj.get('State')) is dict and type(obj['State'].get('ExitCode')) is int, 'exit observation missing')
        obj=retained(query,b['container'],b['container_id'],b['chips'],obj['State']['ExitCode']); labels=obj.get('Config',{}).get('Labels') or {}; need(labels.get('nga.lease_id')==c['lease_id'] and labels.get('nga.task_sha256')==c['task_sha256'], 'task binding changed')
        need(not any(query.conflict(x) for x in b['chips']), 'live device conflict')
        return cl,b,obj
    def build(doc):
        cl,b,obj=evidence(); chips=cl['chips']; need([x for x in doc['allocation'] if x['chip'] in chips]==cl['entries'] and not any(x['chip'] in chips for x in doc['free']), 'ownership generation differs')
        now=R.utc(); after=dict(doc,allocation=[x for x in doc['allocation'] if x['chip'] not in chips],free=sorted(doc['free']+[dict(chip=x,previous_run=c['run'],release_evidence=str(paths(c,'release')[1]),released_utc=now) for x in chips],key=lambda x:x['chip']),updated_utc=now,updated_by='unified resource release')
        return after,dict(chips=chips,entries=cl['entries'],binding=b,exit_code=obj['State']['ExitCode'],started_at=obj['State']['StartedAt'],finished_at=obj['State']['FinishedAt'],scientific_acceptance=False)
    def check(doc,it):
        cl,b,obj=evidence(); need(b==it['binding'] and cl['entries']==it['entries'] and [x for x in doc['allocation'] if x['chip'] in it['chips']]==it['entries'] and (obj['State']['ExitCode'],obj['State']['StartedAt'],obj['State']['FinishedAt'])==(it['exit_code'],it['started_at'],it['finished_at']), 'release generation changed')
    return transaction(c,'release',build,check)

def reconcile(c,query,op):
    need(op in ('claim','release'), 'invalid reconciliation operation')
    need(paths(c,op)[0].exists() or paths(c,op)[1].exists(), 'no existing transaction')
    return (claim if op=='claim' else release)(c,query)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); a=p.parse_args()
    c=json.loads(R.read_bytes(a.config)); validate_config(c)
    print(json.dumps(dict(status='VALID',config_sha256=config_hash(c),mutation_authorized=False)))
if __name__=='__main__': main()
