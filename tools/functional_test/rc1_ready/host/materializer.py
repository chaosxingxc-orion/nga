#!/usr/bin/env python3
"""Freeze identity roster once; publish independent DEV review inputs thereafter.

The inventory and review arguments are exact path/SHA pins. No TEST is launched.
"""
import argparse, datetime, fcntl, json, os, shlex, subprocess, sys, time, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assembler as A, collector, identity_reuse as IR, dev_binding as DB
C = A.C
OUT = Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/test-ready-runtime/materialization')

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def pin(p): return {'path':str(p), 'sha256':C.sha(p)}
def save(p, obj): C.save(p, obj)
def verify(p): C.pinfile(p)
def snapshot(src, dest):
    data = IR.metadata(src)
    if dest.exists():
        if dest.read_bytes() != data: raise ValueError('immutable snapshot changed: '+str(dest))
    else:
        # The watcher lock serializes our writer; no accepted snapshot is replaced.
        with dest.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
    return pin(dest)

def roster(ctx, source_review, scope):
    records={r['id']:r for r in ctx['doc']['roles']}
    ids=C.LANES+C.BASES
    if len(records)!=12 or set(records)!=set(ids): raise ValueError('identity inventory roster differs')
    rows=[]; pending=[]
    config_pin=ctx['doc']['source_acceptance']['checked_required_source_pins']['config.json']
    for member in ids:
        r=records[member]
        row={k:r[k] for k in ('id','arm','seed','terminal_step','model','adapter','identity_sha256')}
        row.update(status='available',size=member.split('-')[0])
        try: IR.select(ctx,row)
        except (IR.PendingIdentity, FileNotFoundError) as e:
            pending.append({'id':member,'artifact':str(e) or 'identity receipt'}); continue
        ev={'base_inventory':{'path':config_pin['path'],'sha256':config_pin['sha256']},
            'tokenizer':pin(Path(row['model'])/'tokenizer.json'),
            'runtime':pin(A.STAGE/'runtime-environment.json'),
            'dev_consumer_review':source_review,'dev_scope':scope}
        if row['arm']=='K1':
            ev.update(publication={k:r['publication'][k] for k in ('path','sha256')},
                      training_terminal={k:r['training_receipts']['COMPLETE.json'][k] for k in ('path','sha256')},
                      smoke_resume={k:r['training_receipts']['train.json'][k] for k in ('path','sha256')},
                      dev_review=source_review)
        row['evidence']=ev; rows.append(row)
    return rows,pending

def committed(out):
    intent_path=out/'ASSEMBLY-INTENT.json'; marker=out/'MATERIALIZED.json'
    if not intent_path.exists():
        if marker.exists() or (out/'campaign').exists(): raise RuntimeError('ambiguous assembly; reconcile')
        return None
    if not marker.exists(): raise RuntimeError('assembly intent without commit; reconcile')
    intent=collector.read(intent_path); done=collector.read(marker)
    if done['intent']!=pin(intent_path): raise ValueError('assembly intent changed')
    for p in (intent['roster'],intent['resources'],intent['inventory'],intent['source_review'],done['graph']): verify(p)
    graph=collector.read(Path(done['graph']['path']))
    for row in collector.read(Path(intent['roster']['path'])):
        for evidence in row['evidence'].values(): verify(evidence)
    if pin(out/'dev-source-review.json')['sha256'] != intent['source_review']['sha256']: raise ValueError('source review snapshot changed')
    inventory=IR.obj(intent['inventory'])
    config_pin=inventory['source_acceptance']['checked_required_source_pins']['config.json']
    if pin(out/'dev-source-config.json')['sha256'] != config_pin['sha256']: raise ValueError('source config snapshot changed')
    if graph['roster_sha256']!=intent['roster']['sha256'] or graph['resources_sha256']!=intent['resources']['sha256'] or len(graph['members'])!=12: raise ValueError('committed graph mismatch')
    for member, item in graph['members'].items():
        verify({'path':item['draft'],'sha256':item['draft_sha256']})
        if Path(item['draft']).resolve() != (out/'campaign'/'drafts'/(member+'.json')).resolve(): raise ValueError('draft path mismatch')
    return graph

def step(out, inventory_pin, source_review_pin):
    out=Path(out).resolve(); out.mkdir(parents=True,exist_ok=True)
    graph=committed(out)
    if graph is not None:
        intent=collector.read(out/'ASSEMBLY-INTENT.json')
        generation=IR.obj(intent['inventory'])
        if intent['source_review'] != source_review_pin or generation['refresh_generation']['parent_inventory'] != inventory_pin:
            raise ValueError('committed input pins differ')
    if graph is None:
        if source_review_pin['path'] != str(DB.REVIEW_ORIGIN): raise ValueError('source review deployment origin differs')
        # New immutable refresh generation per poll; no old inventory is modified.
        gen=out/('identity-inventory-'+uuid.uuid4().hex+'.json')
        try:
            fresh=IR.refresh_inventory(inventory_pin,source_review_pin,gen)
            ctx=IR.load_inventory(fresh,source_review_pin)
            snapshot(source_review_pin,out/'dev-source-review.json')
            config_pin=ctx['doc']['source_acceptance']['checked_required_source_pins']['config.json']
            if config_pin['path'] != str(DB.CONFIG_ORIGIN): raise ValueError('source config deployment origin differs')
            snapshot(config_pin,out/'dev-source-config.json')
            scope_path=out/'dev-scope.json'
            scope={'schema':'rc1-dev-shared-scope-v1','scope':'source and numerical review only', 'member_execution_certified':False,'member_execution_binding':'rc1-trackk-review-v1.own_dev'}
            if scope_path.exists():
                if collector.read(scope_path)!=scope: raise ValueError('scope changed')
            else: save(scope_path,scope)
            rows,pending=roster(ctx,pin(out/'dev-source-review.json'),pin(scope_path))
        except FileNotFoundError as e:
            save(out/'pending.json',{'utc':now(),'identity_pending':[{'artifact':str(e)}],'roles':[]})
            return 'pending'
        if pending:
            save(out/'pending.json',{'utc':now(),'identity_pending':pending,'roles':[]})
            return 'pending'
        rp=out/'roster.json'; res=out/'resources.json'
        resources={i:{'chip':k%8,'dependencies':(['K0','QWEN27B_ENVFIX'] if k%8<4 else ['TRAIN_DEV'])} for k,i in enumerate(C.LANES+C.BASES)}
        # Prior pre-intent files can be replaced only before assembly begins.
        save(rp,rows); save(res,resources)
        intent={'utc':now(),'roster':pin(rp),'resources':pin(res),'inventory':fresh,'source_review':source_review_pin}
        ip=out/'ASSEMBLY-INTENT.json'
        with ip.open('x') as f:
            json.dump(intent,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
        graph=A.assemble(str(rp),str(res),str(out/'campaign'),fresh,source_review_pin)
        save(out/'MATERIALIZED.json',{'utc':now(),'intent':pin(ip),'graph':pin(out/'campaign/graph.json'),'members':len(graph['members']),'status':'needs_independent_review'})
        graph=committed(out)
    # Source config/review snapshots are immutable; actual comparison stays at its
    # reviewed configuration's output path, as required by its source contract.
    config=collector.read(out/'dev-source-config.json')
    comparison=Path(config['output'])/'comparison.json'
    # A published global refusal remains a refusal even after all members were
    # snapshotted. A missing/racing comparison is handled per member as pending.
    try:
        published=DB.decode(DB.read(comparison))
        if published.get('status')=='REFUSED_CONTRADICTION' or published.get('queue_failures') or any(x.get('status')=='REFUSED_CONTRADICTION' for x in published.get('operands',[])):
            raise DB.Contradiction('global DEV contradiction')
    except DB.Pending:
        pass
    roles=[]
    for member,item in graph['members'].items():
        c=collector.read(Path(item['draft'])); root=Path(c['host']['dev_evidence_dir']); bundle=root/'bundle.json'
        try:
            if bundle.exists():
                DB._local(c,DB.decode(DB.read(bundle)))
                result=pin(bundle)
            else:
                review_path=Path(item['review'])
                if review_path.exists() and collector.read(review_path).get('reviewed') is True:
                    raise DB.Contradiction('reviewed member bundle missing')
                result=DB.publish_member(c,comparison,Path(source_review_pin['path']),Path(intent_config_path(out)))
            review_input=root/'review-input.json'
            data={'schema':'rc1-trackk-review-input-v1','member':member,'config_sha256':C.digest({k:v for k,v in c.items() if k!='review'}),'own_dev':result}
            if review_input.exists():
                if collector.read(review_input)!=data: raise ValueError('review input changed')
            else: save(review_input,data)
            roles.append({'id':member,'status':'ready','review_input':str(review_input)})
        except DB.Pending as e:
            roles.append({'id':member,'status':'pending','pending':[str(e)]})
    save(out/'pending.json',{'utc':now(),'identity_pending':[],'roles':roles})
    return 'materialized'

def intent_config_path(out):
    intent=collector.read(out/'ASSEMBLY-INTENT.json')
    ctx=IR.load_inventory(intent['inventory'],intent['source_review'])
    return ctx['doc']['source_acceptance']['checked_required_source_pins']['config.json']['path']

def result_tick(config,out):
    runner=Path(__file__).resolve().parent.parent/'package/watcher.py'
    result=subprocess.run([sys.executable,'-B','-P',str(runner),'--config',str(config),'--out',str(out/'same-test'),'--once'],check=False)
    if result.returncode: raise ValueError('same-TEST collector failed; see same-test/heartbeat.json')
    status=collector.read(out/'same-test/heartbeat.json')
    if status['status']=='error': raise ValueError('same-TEST collector failed; see same-test/heartbeat.json')
    return status

def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=OUT); p.add_argument('--identity-inventory-pin',type=Path,required=True); p.add_argument('--source-review-pin',type=Path,required=True); p.add_argument('--once',action='store_true'); p.add_argument('--result-config',type=Path); a=p.parse_args()
    out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    with (out/'watcher.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'EXIT.json').exists(): raise RuntimeError('terminal exists; reconcile')
        inventory=collector.read(a.identity_inventory_pin); review=collector.read(a.source_review_pin)
        cmd=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--out',str(out),'--identity-inventory-pin',str(a.identity_inventory_pin.resolve()),'--source-review-pin',str(a.source_review_pin.resolve())]
        if a.result_config: cmd+=['--result-config',str(a.result_config.resolve())]
        (out/'RELAUNCH.sh').write_text('#!/bin/sh\nexec '+shlex.join(cmd)+'\n')
        save(out/'LAUNCH.json',{'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'utc':now(),'command':cmd})
        try:
            while True:
                result=step(out,inventory,review); roles=collector.read(out/'pending.json')['roles']
                beat={'utc':now(),'status':result,'completed':sum(x['status']=='ready' for x in roles),'total':12}
                if a.result_config:
                    collected=result_tick(a.result_config,out); beat['result_collector']=collected['status']
                    if collected['status']=='ready_for_consumer':
                        save(out/'heartbeat.json',beat); save(out/'EXIT.json',{'exit_code':0,'utc':now(),'status':'collected','consumer_exit':collected['consumer_exit']}); return 0
                save(out/'heartbeat.json',beat); print(json.dumps(beat),flush=True)
                if a.once: return 0 if result=='materialized' else 2
                time.sleep(600)
        except BaseException as e:
            save(out/'EXIT.json',{'exit_code':1,'utc':now(),'error':str(e)}); raise
if __name__=='__main__': sys.exit(main())
