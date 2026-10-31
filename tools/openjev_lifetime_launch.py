#!/usr/bin/env python3
"""E40 guarded detached launch; no implicit resource reclamation or Docker restart."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import types


def launch(path, pin):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Externally pinned plan differs')
    p=json.loads(raw);out=path.parent
    if p['out']!=str(out):raise ValueError('Plan location differs')
    # Authenticate local Python closure before any path-based helper import.
    for f in out.glob('*.py'):
        if f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=p['files'].get(str(f)):
            raise ValueError('Unbound executable '+str(f))
    def module(n):
        f=out/n;data=f.read_bytes()
        if hashlib.sha256(data).hexdigest()!=p['files'].get(str(f)):raise ValueError('Executable changed')
        m=types.ModuleType('e40_launch_'+n);m.__file__=str(f);exec(compile(data,str(f),'exec'),m.__dict__);return m
    durable=module('e38_evidence.py');q=module('jeval_reference_queue.py')
    old=module('prepare_openjev_path_trace.py');proto=module('openjev_lifetime_protocol.py')
    proto.validate_plan(p);old.host(q)
    e=durable.Evidence(q)
    # Host launch validates controls only; full native/model closure is rehashed by the retained driver.
    inherited=e.load(p['e38_plan'])['files']
    proto.require(e.sha(p['e38_plan'])==p['e38_plan_sha256'],'Source E38 plan differs')
    proto.require(all(p['files'].get(k)==v for k,v in inherited.items()),'Inherited dependency omitted')
    controls={k:v for k,v in p['files'].items() if k not in inherited}
    controls[p['source_config']]=p['source_config_sha256']
    old.small_frozen(e,controls)
    for n in ['PARENT_REVIEW.json','INDEPENDENT_REVIEW.json']:
        r=e.load(out/n)
        proto.require(r.get('approved') is True and r['approved_plan_sha256']==pin,'Exact reviewed plan required')
        if n=='INDEPENDENT_REVIEW.json':proto.require(e.sha(r['review_path'])==r['review_sha256'],'Review bytes differ')
    spec=e.load(p['container_spec'])
    proto.require(spec['Image']==proto.IMAGE and spec['Cmd']==['bash',p['wrapper']]
        and not spec['HostConfig'].get('AutoRemove'),'Retained exact wrapper required')
    device=[d for d in spec['HostConfig']['Devices'] if d['PathOnHost'].startswith('/dev/davinci') and d['PathOnHost'][12:].isdigit()]
    proto.require(len(device)==1 and device[0]['PathOnHost']=='/dev/davinci1','Only physical chip 1 allowed')
    proto.require(not any(spec['HostConfig'].get(k) for k in ['Privileged','DeviceRequests','DeviceCgroupRules','Mounts','PidMode']),
                  'Unexpected device exposure')
    return transaction(p, pin, out, spec, q, e, durable, old, proto,
        Path('/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json'))


def transaction(p, pin, out, spec, q, e, durable, old, proto, allocation):
    lockfd=os.open(str(allocation)+'.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o644)
    with os.fdopen(lockfd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        proto.require(not any((out/n).exists() for n in ['COMPLETE.json','FAILED_GENERATION.json','EXIT']),
                      'Terminal/uncertain generation cannot relaunch')
        current=q.load(allocation);run='reference_inference/'+out.name
        owned=old.allocation_check(current,1,run,allow_owned=True)
        actual=q.inspect(p['container']);intent_path=out/'LAUNCH_INTENT.json'
        if actual is not None:
            q.binding(actual,spec)
            proto.require(actual['State']['Status'] in ('created','running'),'Docker restart requires new generation')
        expected=dict(plan_sha256=pin,spec_sha256=e.sha(p['container_spec']),run=run,chip=1)
        if intent_path.exists():proto.require(q.load(intent_path)==expected,'Launch intent differs')
        else:
            proto.require(not owned and actual is None,'Unowned launch history required')
            durable.publish_new(intent_path,expected)
        if not owned:
            proto.require(actual is None,'Container exists before resource claim')
            before=json.loads(json.dumps(current));current['free']=[x for x in current['free'] if x['chip']!=1]
            current['allocation'].append(dict(chip=1,run=run,owner='E40 full-shape lifetime diagnostic',claimed_utc=q.utc(),
                release_when='independent complete receipt verification, actual exit and reviewed release transaction'))
            claim=out/'CLAIM.json'
            claim_pending=claim.with_name(claim.name+'.pending')
            if claim.exists() or claim_pending.exists():
                saved=q.load(claim if claim.exists() else claim_pending)
                proto.require(saved['before']==before and saved['plan_sha256']==pin,'Claim recovery differs')
                recovered=saved['after']
                proto.require([x for x in recovered['allocation'] if x.get('chip')!=1]==before['allocation']
                    and recovered['free']==[x for x in before['free'] if x.get('chip')!=1]
                    and len([x for x in recovered['allocation'] if x.get('chip')==1 and x.get('run')==run])==1,
                    'Pending claim transition differs')
                proto.require(all(recovered[k]==v for k,v in before.items() if k not in ('allocation','free')),
                    'Pending claim changes unrelated metadata')
                current=recovered
                durable.publish_new(claim,saved)
            else:durable.publish_new(claim,dict(plan_sha256=pin,before=before,after=current))
            e.verify(metadata_only=True);q.atomic(allocation,current);durable.sync_directory(allocation.parent)
        else:
            claim=q.load(out/'CLAIM.json')
            proto.require(claim['plan_sha256']==pin and any(x['run']==run and x['chip']==1 for x in claim['after']['allocation']),
                          'Existing owner lacks exact claim')
        if actual is None:
            proto.require(not (out/'LAUNCH_RECEIPT.json').exists()
                and not (out/'LAUNCH_RECEIPT.json.pending').exists(), 'Receipt without retained Docker')
            old.free_now(q,1)
            q.docker('POST','/containers/create?name='+p['container'],spec);actual=q.inspect(p['container'])
        q.binding(actual,spec)
        receipt=out/'LAUNCH_RECEIPT.json'
        receipt_fields=dict(container_id=actual['Id'],image=proto.IMAGE,command=spec['Cmd'],
            entrypoint=spec['Entrypoint'],plan_sha256=pin,wrapper_sha256=e.sha(p['wrapper']),
            parent_review_sha256=e.sha(out/'PARENT_REVIEW.json'),launcher_hostname=socket.gethostname())
        pending=receipt.with_name(receipt.name+'.pending')
        if not receipt.exists() or pending.exists():
            proto.require(actual['State']['Status']=='created','Missing or uncertain receipt for started Docker')
            if pending.exists():
                value=q.load(pending)
                proto.require(set(value)==set(receipt_fields)|{'launcher_utc'}
                    and all(value[k]==v for k,v in receipt_fields.items())
                    and type(value['launcher_utc']) is str and bool(value['launcher_utc']), 'Pending receipt differs')
            else:value=dict(**receipt_fields,launcher_utc=q.utc())
            durable.publish_new(receipt,value)
        saved=q.load(receipt)
        proto.require(set(saved)==set(receipt_fields)|{'launcher_utc'}
            and all(saved[k]==v for k,v in receipt_fields.items()),'Receipt identity differs')
        q.binding(actual,spec,q.load(receipt))
        proto.require(q.load(receipt)['plan_sha256']==pin,'Receipt plan differs')
        # The wrapper convenience pin is checked against the external review-bound pin before start.
        proto.require((out/'PLAN.sha256').read_text()==pin+'\n','Wrapper pin differs')
        if actual['State']['Status']=='running':
            # A start response can be lost after successful device acquisition.
            # Authenticate retained ownership/intent/receipt, then acknowledge it;
            # demanding an empty NPU would reject the very job being recovered.
            for item in q.docker('GET','/containers/json'):
                proto.require(item['Id']==actual['Id'] or not q.chip_access(q.inspect(item['Id']),1),
                    'Other live Docker resource conflict')
        else:
            old.free_now(q,1,ignore=actual['Id'])
            e.verify(metadata_only=True);q.docker('POST','/containers/'+actual['Id']+'/start')
        return dict(container_id=actual['Id'],status=q.inspect(p['container'])['State']['Status'],physical_chip=1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True)
    a=p.parse_args();print(json.dumps(launch(a.plan.absolute(),a.plan_sha256)))
