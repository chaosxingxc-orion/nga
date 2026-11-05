import copy
import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from tools import unified_resource_lease_v1 as U
from tools import r3_resource_adapter as R


def race(config, out):
    try: out.put(('ok', U.claim(config, Query())['chips']))
    except Exception as e: out.put(('error', str(e)))

class Query:
    def __init__(self, objects=None): self.objects=objects or {}
    def inspect(self,name): return copy.deepcopy(self.objects.get(name))
    def conflict(self,chip): return False

def obj(chips, name='old', code=1, lease=None, task=None):
    return dict(Id=('a' if name=='old' else 'b')*64,Name='/'+name,RestartCount=0,State=dict(Status='exited',Running=False,ExitCode=code,StartedAt='start',FinishedAt='finish'),HostConfig=dict(AutoRemove=False,Devices=[dict(PathOnHost=f'/dev/davinci{i}',PathInContainer=f'/dev/davinci{i}') for i in chips]),Config=dict(Labels={'nga.lease_id':lease,'nga.task_sha256':task}))

class LeaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name); self.alloc=str(self.root/'alloc.json'); self.old=obj([0,1,2,3]); self.q=Query({'old':self.old}); self.pre={}; free=[]
        for chip in range(4):
            d=self.root/f'old{chip}'; d.mkdir(); cp=d/'CLAIM.json'; rp=d/'RELEASE.json'
            entry=dict(chip=chip,run='old',owner='prior'); before=dict(allocation=[entry],free=[],pending_claims=[]); fe=dict(chip=chip,previous_run='old',release_evidence=str(rp),released_utc='then'); after=dict(allocation=[],free=[fe],pending_claims=[])
            claim=dict(schema='r3-resource-claim-v1',chip=chip,run='old',allocation=self.alloc,entry=entry); R.write_atomic(cp,claim)
            rel=dict(schema='r3-resource-release-v1',chip=chip,run='old',allocation_before=before,allocation_after=after,allocation_before_sha256=U.digest(before),allocation_after_sha256=U.digest(after),scientific_acceptance=False,exit_code=1,container='old'+str(chip),container_id='a'*64,container_started_at='start',container_finished_at='finish'); R.write_atomic(rp,rel)
            self.pre[str(chip)]=dict(claim=self.pin(cp),release=self.pin(rp),container=None,terminal=None); free.append(fe)
        # Each single predecessor had exactly one device; mock each by device based on name below.
        self.q=SingleQuery()
        R.write_atomic(self.alloc,dict(allocation=[],free=free,pending_claims=[],other={'keep':1}))
        self.policy=self.root/'policy.json'; R.write_atomic(self.policy,dict(schema='nga-engineering-release-policy-v1',new_experiment_dispatch='allow'))
        self.accept=self.root/'accept.json'; self.c=self.config('one')
    def pin(self,p): return dict(path=str(p),sha256=R.sha_bytes(R.read_bytes(p)))
    def config(self,lease,count=1,ids=None):
        c=dict(schema='unified-resource-lease-config-v1',allocation=self.alloc,journal=str(self.root/'journal'),lease_id=lease,owner='owner',run=lease,task_sha256='c'*64,eligible_device_ids=ids or [0,1,2,3],device_count=count,priority=3,priority_override=None,policy=self.pin(self.policy),acceptance=None,predecessors={str(i):self.pre[str(i)] for i in (ids or [0,1,2,3])})
        ap=self.root/(lease+'-accept.json'); R.write_atomic(ap,dict(schema='unified-resource-acceptance-v1',decision='accept',policy_sha256=c['policy']['sha256'],config_sha256=U.config_hash(c))); c['acceptance']=self.pin(ap); return c
    def bind(self, chips):
        self.q.bound=obj(chips,'new',7,self.c['lease_id'],self.c['task_sha256']); U.bind_container(self.c,self.q,'new','b'*64)
    def test_claim_bind_release_failure_exit(self):
        cl=U.claim(self.c,self.q); self.assertEqual(cl['chips'],[0]); self.bind([0]); rel=U.release(self.c,self.q); self.assertEqual(rel['exit_code'],7); self.assertFalse(rel['scientific_acceptance']); doc=R.load(self.alloc); self.assertEqual(doc['other'],{'keep':1}); self.assertEqual(doc['pending_claims'],[])
    def test_wrong_devices_and_forged_binding(self):
        U.claim(self.c,self.q); self.q.bound=obj([1],'new',0,'one','c'*64)
        with self.assertRaises(ValueError): U.bind_container(self.c,self.q,'new','b'*64)
        self.q.bound=obj([0],'new',0,'one','c'*64); U.bind_container(self.c,self.q,'new','b'*64); self.q.bound['RestartCount']=1
        with self.assertRaises(ValueError): U.release(self.c,self.q)
        self.q.bound['RestartCount']=0; self.q.bound['Config']['Labels']['nga.task_sha256']='d'*64
        with self.assertRaises(ValueError): U.release(self.c,self.q)
    def test_crash_recovery_and_divergence(self):
        original=R.write_atomic
        for failure in ('intent','ledger'):
            with self.subTest(failure=failure):
                c=self.config(failure,ids=[0] if failure=='intent' else [1]); fired=[False]
                def crash(path,value):
                    result=original(path,value)
                    if not fired[0] and ((failure=='intent' and str(path).endswith('claim.intent.json')) or (failure=='ledger' and str(path)==self.alloc)):
                        fired[0]=True; raise OSError('simulated crash')
                    return result
                with mock.patch.object(R,'write_atomic',side_effect=crash):
                    with self.assertRaises(OSError): U.claim(c,self.q)
                self.assertEqual(U.reconcile(c,self.q,'claim')['chips'],[0 if failure=='intent' else 1]); self.assertEqual(U.claim(c,self.q)['chips'],[0 if failure=='intent' else 1])
    def test_diverged_intent_never_overwrites_foreign_generation(self):
        original=R.write_atomic
        def crash(path,value):
            result=original(path,value)
            if str(path).endswith('claim.intent.json'): raise OSError('crash')
            return result
        with mock.patch.object(R,'write_atomic',side_effect=crash):
            with self.assertRaises(OSError): U.claim(self.c,self.q)
        doc=R.load(self.alloc); doc['other']['foreign']=True; R.write_atomic(self.alloc,doc)
        with self.assertRaisesRegex(ValueError,'diverged'): U.reconcile(self.c,self.q,'claim')
        self.assertEqual(R.load(self.alloc),doc)
    def test_release_recovery_after_commit(self):
        U.claim(self.c,self.q); self.bind([0]); original=R.write_atomic; fired=[False]
        def crash(path,value):
            result=original(path,value)
            if str(path)==self.alloc and not fired[0]: fired[0]=True; raise OSError('crash')
            return result
        with mock.patch.object(R,'write_atomic',side_effect=crash):
            with self.assertRaises(OSError): U.release(self.c,self.q)
        self.assertEqual(U.reconcile(self.c,self.q,'release')['exit_code'],7)
        self.assertEqual(U.release(self.c,self.q)['exit_code'],7)
    def test_priority_override_preserves_pending(self):
        doc=R.load(self.alloc); doc['pending_claims']=[{'owner':'other','priority':99}]; R.write_atomic(self.alloc,doc)
        override=self.root/'override.json'; R.write_atomic(override,dict(schema='unified-priority-override-v1',decision='authorize',allocation=self.alloc,lease_id='one',priority=3,pending_sha256=U.digest(doc['pending_claims']),task_sha256='c'*64))
        self.c['priority_override']=self.pin(override); ap=self.root/'one-accept.json'; R.write_atomic(ap,dict(schema='unified-resource-acceptance-v1',decision='accept',policy_sha256=self.c['policy']['sha256'],config_sha256=U.config_hash(self.c))); self.c['acceptance']=self.pin(ap)
        U.claim(self.c,self.q); self.assertEqual(R.load(self.alloc)['pending_claims'],doc['pending_claims'])
    def test_policy_hold_and_pending(self):
        d=R.load(self.alloc); d['pending_claims']=[{'owner':'other'}]; R.write_atomic(self.alloc,d)
        with self.assertRaises(ValueError): U.claim(self.c,self.q)
        R.write_atomic(self.policy,dict(schema='nga-engineering-release-policy-v1',new_experiment_dispatch='hold')); c=self.config('held')
        with self.assertRaisesRegex(ValueError,'HOLD'): U.claim(c,self.q)
    def mutable_config(self, lease='mutable'):
        dispatch=self.root/(lease+'-dispatch.json')
        R.write_atomic(dispatch,dict(schema='nga-engineering-release-policy-v1',new_experiment_dispatch='allow'))
        c=self.config(lease); c['dispatch_policy']=str(dispatch)
        ap=Path(c['acceptance']['path']); R.write_atomic(ap,dict(schema='unified-resource-acceptance-v1',decision='accept',policy_sha256=c['policy']['sha256'],config_sha256=U.config_hash(c))); c['acceptance']=self.pin(ap)
        return c
    def hold(self,c):
        U.update_dispatch_policy(c,dict(schema='nga-engineering-release-policy-v1',new_experiment_dispatch='hold'))
    def test_hold_allows_exited_prior_binding_release(self):
        self.c=self.mutable_config(); U.claim(self.c,self.q); self.bind([0])
        self.q.bound['State'].update(Status='running',Running=True)
        self.hold(self.c)
        with self.assertRaises(ValueError): U.release(self.c,self.q)
        self.q.bound['State'].update(Status='exited',Running=False)
        self.assertEqual(U.release(self.c,self.q)['chips'],[0])
    def test_hold_blocks_fresh_and_before_image_and_bind(self):
        c=self.mutable_config(); original=R.write_atomic
        def crash(path,value):
            original(path,value)
            if str(path).endswith('claim.intent.json'): raise OSError('crash')
        with mock.patch.object(R,'write_atomic',side_effect=crash):
            with self.assertRaises(OSError): U.claim(c,self.q)
        self.hold(c)
        with self.assertRaisesRegex(ValueError,'HOLD'): U.reconcile(c,self.q,'claim')
        fresh=self.mutable_config('fresh'); self.hold(fresh)
        with self.assertRaisesRegex(ValueError,'HOLD'): U.claim(fresh,self.q)
        self.assertEqual(R.load(self.alloc)['allocation'],[])
        U.update_dispatch_policy(c,dict(schema='nga-engineering-release-policy-v1',new_experiment_dispatch='allow'))
        U.reconcile(c,self.q,'claim'); self.hold(c)
        with self.assertRaisesRegex(ValueError,'HOLD'): U.bind_container(c,self.q,'new','b'*64)
        self.assertFalse(U.paths(c,'binding')[1].exists())
    def test_committed_claim_inspection_and_publication_under_hold(self):
        c=self.mutable_config(); original=R.write_atomic
        def crash(path,value):
            original(path,value)
            if str(path)==self.alloc: raise OSError('crash')
        with mock.patch.object(R,'write_atomic',side_effect=crash):
            with self.assertRaises(OSError): U.claim(c,self.q)
        self.hold(c)
        self.assertEqual(U.reconcile(c,self.q,'claim')['chips'],[0])
        self.assertEqual(U.claim(c,self.q)['chips'],[0])
        with self.assertRaisesRegex(ValueError,'HOLD'): U.bind_container(c,self.q,'new','b'*64)
    def test_wrong_acceptance_and_foreign_binding_cannot_release(self):
        self.c=self.mutable_config(); U.claim(self.c,self.q); self.bind([0]); self.hold(self.c)
        original=R.read_bytes(self.c['acceptance']['path']); Path(self.c['acceptance']['path']).write_text('{}')
        with self.assertRaises(ValueError): U.release(self.c,self.q)
        Path(self.c['acceptance']['path']).write_bytes(original)
        bp=U.paths(self.c,'binding')[1]; binding=R.load(bp); binding['lease_id']='foreign'; R.write_atomic(bp,binding)
        with self.assertRaises(ValueError): U.release(self.c,self.q)
        self.assertEqual(len(R.load(self.alloc)['allocation']),1)
    def test_policy_writer_serializes_with_claim(self):
        c=self.mutable_config(); entered=threading.Event(); proceed=threading.Event(); done=threading.Event(); errors=[]
        class PausedQuery(SingleQuery):
            def inspect(self,name):
                entered.set()
                if not proceed.wait(5): raise RuntimeError('timeout')
                return super().inspect(name)
        def do_claim():
            try: U.claim(c,PausedQuery())
            except Exception as e: errors.append(e)
        def do_hold():
            try: self.hold(c)
            except Exception as e: errors.append(e)
            finally: done.set()
        a=threading.Thread(target=do_claim); a.start(); self.assertTrue(entered.wait(5))
        b=threading.Thread(target=do_hold); b.start(); self.assertFalse(done.wait(0.1)); proceed.set(); a.join(5); b.join(5)
        self.assertFalse(a.is_alive() or b.is_alive()); self.assertEqual(errors,[])
        self.assertEqual(U.claim(c,self.q)['chips'],[0])
        with self.assertRaisesRegex(ValueError,'HOLD'): U.bind_container(c,self.q,'new','b'*64)
    def test_noncooperative_identical_pin_replacement_before_commit(self):
        c=self.mutable_config(); original=R.write_atomic; fired=[False]
        def replace(path,value):
            original(path,value)
            if str(path).endswith('claim.intent.json') and not fired[0]:
                fired[0]=True; ap=Path(c['acceptance']['path']); replacement=ap.with_suffix('.replacement'); replacement.write_bytes(ap.read_bytes()); replacement.replace(ap)
        with mock.patch.object(R,'write_atomic',side_effect=replace):
            with self.assertRaisesRegex(ValueError,'authority file replaced'): U.claim(c,self.q)
        self.assertEqual(R.load(self.alloc)['allocation'],[])
    def test_group_atomic(self):
        # group predecessor using actual qwen38 receipt schema
        d=self.root/'group'; d.mkdir(); cp=d/'CLAIM.json'; rp=d/'RELEASE.json'; chips=[0,1,2,3]; entries=[dict(chip=i,run='old') for i in chips]; ca=dict(allocation=entries,free=[],pending_claims=[]); free=[dict(chip=i,previous_run='old',release_evidence=str(rp),released_utc='then') for i in chips]; ra=dict(allocation=[],free=free,pending_claims=[])
        claim=dict(schema='qwen38-group-transaction-v1',op='claim',run='old',allocation=self.alloc,chips=chips,entries=entries,after=ca,after_sha256=U.digest(ca)); R.write_atomic(cp,claim); pin=self.pin(cp)
        R.write_atomic(rp,dict(schema=claim['schema'],op='release',run='old',allocation=self.alloc,chips=chips,entries=entries,after=ra,after_sha256=U.digest(ra),claim_sha256=pin['sha256'],absent=False,container='old',container_id='a'*64,utc='then'))
        co=d/'CONTAINER.json'; te=d/'TERMINAL.json'; R.write_atomic(co,dict(claim_sha256=pin['sha256'],id='a'*64,config_sha256='e'*64)); R.write_atomic(te,dict(container_id='a'*64,config_sha256='e'*64,exit_code=1))
        self.pre={str(i):dict(claim=pin,release=self.pin(rp),container=self.pin(co),terminal=self.pin(te)) for i in chips}; R.write_atomic(self.alloc,ra); c=self.config('group',4); cl=U.claim(c,Query({'old':self.old})); self.assertEqual(cl['chips'],chips); self.assertEqual(len(R.load(self.alloc)['allocation']),4)
    def test_two_process_race(self):
        # Fork inherits realistic Docker query as a process-local test double.
        ctx=multiprocessing.get_context('fork'); out=ctx.Queue(); a=self.config('racea',ids=[0]); b=self.config('raceb',ids=[0]);
        # Query in the child supplies the single predecessor observation.
        global Query
        original=Query; Query=SingleQuery
        try:
            ps=[ctx.Process(target=race,args=(c,out)) for c in (a,b)]
            for p in ps:p.start()
            for p in ps:p.join(10); self.assertEqual(p.exitcode,0)
            results=[out.get(timeout=2)[0] for _ in ps]; self.assertEqual(sorted(results),['error','ok'])
        finally: Query=original

class SingleQuery:
    def __init__(self): self.bound=None; self.next_chip=0
    def inspect(self,name):
        if name=='new': return copy.deepcopy(self.bound)
        # All four single fixtures use a shared retained name; select the currently queried chip.
        return obj([int(name[3:])])
    def conflict(self,chip): self.next_chip=chip; return False

if __name__=='__main__': unittest.main()
