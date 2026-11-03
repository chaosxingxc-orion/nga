import copy
import contextlib
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools.r3_named_forward_v1 import NamedForward, PHASES
from tools.r3_named_trace_join_v1 import join, iter_events
from tools import r3_profile_named_host_v1 as H
from tools import r3_eval_profile_named_runtime_v1 as B
from tools import r3_eval_profile_probe as P
from tools.test_r3_eval_profile_probe import FakeFrozenScorer

PIN='a'*64
CELL='K/decision-v7/dev/clean'

def fixture():
    records=[];events=[]
    for phase in PHASES:
        for i in range(1,4):
            name=f'nga.forward/{PIN}/1/{phase}/{hashlib.sha256(CELL.encode()).hexdigest()}/{i}'
            records.append(dict(name=name,phase=phase,status='returned',ordinal=i,cell=CELL))
            if phase!='trace':continue
            start=i*100
            events.extend([dict(name=name,ph='X',pid=1,tid=1,ts=start,dur=40,cat='cpu_op'),
                dict(name='torch_to_npu',ph='s',cat='async_npu',id=i,pid=1,tid=1,ts=start+2),
                dict(name='torch_to_npu',ph='f',cat='async_npu',id=i,pid=9,tid=2,ts=start+90),
                dict(name='kernel',ph='X',pid=9,tid=2,ts=start+90,dur=3,args={'Task Type':'KERNEL_AIVEC'})])
    return events,dict(schema='named-forward-manifest-v1',plan_sha256=PIN,attempt=1,total_forwards=21,records=records)

class Tests(unittest.TestCase):
    def test_npu_terminal_identity_and_handoff_failures(self):
        for mutation in ('valid','foreign_generation','boolean_exit','wrong_attempt','scientific_true','handoff_failure'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as td:
                root=Path(td);(root/'host_attempts/1').mkdir(parents=True);(root/'attempts/1').mkdir(parents=True)
                terminal={'exit_code':0,'attempt':1,'plan_sha256':'correct','scientific_acceptance':False}
                if mutation=='foreign_generation':terminal['plan_sha256']='foreign'
                elif mutation=='boolean_exit':terminal['exit_code']=False
                elif mutation=='wrong_attempt':terminal['attempt']=2
                elif mutation=='scientific_true':terminal['scientific_acceptance']=True
                (root/'attempts/1/EXIT.json').write_text(json.dumps(terminal))
                d={'out':str(root),'container':'fixture','image_sha256':'image','chip':1,'resource_base':{},'resource':{'path':'resource'}};args=SimpleNamespace(plan='plan',sha256='correct',review='review',review_sha256='reviewpin',attempt=1)
                actual={'Id':'cid','Image':'image','HostConfig':{'AutoRemove':False},'Config':{'Cmd':['runtime']},'State':{'Status':'exited','ExitCode':0,'Running':False}}
                with patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H,'preflight'),patch.object(H,'module',return_value=SimpleNamespace(live_chip_conflict=lambda *a:False)),patch.object(H,'inspect',side_effect=[None,actual,actual]),patch.object(H,'command',return_value=['docker','image','runtime']),patch.object(H.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as process,patch.object(H.subprocess,'Popen',return_value=SimpleNamespace(wait=lambda **kw:0)),patch.object(H,'start_cpu',side_effect=RuntimeError('handoff failed') if mutation=='handoff_failure' else None) as cpu:
                    H.supervise(args)
                end=json.loads((root/'host_attempts/1/EXIT.json').read_text());good=mutation in ('valid','handoff_failure')
                self.assertEqual(end['exit_code'],0 if good else 1);self.assertIs(end['runner_terminal_matches'],good);self.assertEqual(cpu.called,good)
                self.assertTrue(any('release' in call.args[0] for call in process.call_args_list))
                self.assertEqual((root/'host_attempts/1/CPU_HANDOFF_ERROR.json').exists(),mutation=='handoff_failure')
                self.assertEqual(end['plan_sha256'],'correct');self.assertEqual(end['attempt'],1)

    def test_cpu_supervisor_exception_leaves_bounded_failure_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            plan=Path(td)/'plan.json';plan.write_text(json.dumps({'out':td}));args=SimpleNamespace(plan=str(plan),sha256=PIN,attempt=1)
            with patch.object(H,'_supervise_cpu',side_effect=RuntimeError('offline failure')):
                with self.assertRaises(RuntimeError):H.supervise_cpu(args)
            end=json.loads((Path(td)/'cpu/host_attempts/1/EXIT.json').read_text())
            self.assertEqual(end['exit_code'],1);self.assertIsNone(end['container_exit_code']);self.assertFalse(end['runner_terminal_matches']);self.assertEqual(end['plan_sha256'],PIN)

    def test_reject_invalid_numeric_types_and_nonfinite_aggregates(self):
        for key,value in [('dur',-30),('dur','NaN'),('dur','Infinity'),('dur',True),('dur','1e9999'),('ts',-1),('pid',True),('tid','2')]:
            with self.subTest(key=key,value=value):
                e,m=fixture();e[3][key]=value
                with self.assertRaises(ValueError):join(e,m,PIN)
        e,m=fixture()
        for event in e:
            if event.get('cat')=='async_npu':event['name']='foreign'
        with self.assertRaisesRegex(ValueError,'foreign flow'):join(e,m,PIN)

    def test_complete_strict_streaming_envelope(self):
        e,m=fixture();original=json.dumps({'metadata':{'version':1},'traceEvents':e,'displayTimeUnit':'us'})
        malformed=[original[:-1],original+' garbage',original.replace('"dur": 3','"dur": -100, "dur": 3',1),original.replace('"dur": 3','"dur": NaN',1),original.replace('"dur": 3','"dur": Infinity',1),original.replace('"version": 1','"version": 1, "version": 2'),original[:-1]+', "traceEvents": []}',original.replace('"displayTimeUnit": "us"','"displayTimeUnit": "us",'),json.dumps(e)[:-1]+',]']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.json'
            for data in malformed:
                with self.subTest(data=data[-100:]):
                    p.write_text(data)
                    with self.assertRaises(ValueError):join(iter_events(p),m,PIN)
            p.write_text(original+'   \n');self.assertEqual(join(iter_events(p),m,PIN)['forward_ranges'],3)
            padded={'metadata':{'padding':'x'*70000},'traceEvents':e,'suffix':{'padding':'y'*70000}}
            p.write_text(json.dumps(padded));self.assertEqual(join(iter_events(p),m,PIN)['forward_ranges'],3)

    def test_batch_composition_passes_explicit_phase_cell_and_restores_scope(self):
        seen=[]
        class Observer:
            @contextlib.contextmanager
            def scope(self,phase,cell,rows):
                seen.append((phase,cell,[r['id'] for r in rows]));yield
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'attempts/1').mkdir(parents=True)
            result=B.batches(P,FakeFrozenScorer(),{CELL:[{'id':'q','row':{'levels':[{},{}]}}]},root,1,PIN,forward_observer=Observer())
            self.assertEqual([x[0] for x in seen],list(PHASES));self.assertTrue(all(x[1:]==(CELL,['q']) for x in seen));self.assertTrue(result['all_raw_exact'])

    def test_streaming_array_and_object_envelopes(self):
        e,m=fixture()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.json'
            for value in (e,{'traceEvents':e,'displayTimeUnit':'us'}):
                p.write_text(json.dumps(value));self.assertEqual(list(iter_events(p)),e)
                self.assertEqual(join(iter_events(p),m,PIN)['forward_ranges'],3)
            p.write_text(json.dumps(e)[:-5])
            with self.assertRaises(ValueError):list(iter_events(p))

    def test_cross_domain_timestamp_order_is_not_invented(self):
        e,m=fixture();e[2]['ts']=10;e[3]['ts']=10
        self.assertEqual(join(e,m,PIN)['status'],'PASS_NAMED_FORWARD_CORRELATION')

    def test_join_uses_flow_identity_not_device_clock_overlap(self):
        events,m=fixture();r=join(events,m,PIN)
        self.assertEqual(r['forward_ranges'],3);self.assertTrue(r['partition_complete'])
        self.assertEqual(sum(x['tasks'] for x in r['per_forward'].values()),3)

    def test_missing_duplicate_foreign_ambiguous_counterexamples(self):
        for mutation in ('missing_range','duplicate_range','foreign_range','missing_endpoint','duplicate_endpoint','foreign_manifest','ambiguous_target','ambiguous_range'):
            with self.subTest(mutation=mutation):
                e,m=fixture()
                if mutation=='missing_range':e.pop(0)
                elif mutation=='duplicate_range':e.append(copy.deepcopy(e[0]))
                elif mutation=='foreign_range':e[0]['name']=e[0]['name'].replace(PIN,'b'*64)
                elif mutation=='missing_endpoint':e.pop(2)
                elif mutation=='duplicate_endpoint':e.append(copy.deepcopy(e[1]))
                elif mutation=='foreign_manifest':m['plan_sha256']='b'*64
                elif mutation=='ambiguous_target':e.append(copy.deepcopy(e[3]))
                elif mutation=='ambiguous_range':e[0]['dur']=250
                with self.assertRaises(ValueError):join(e,m,PIN)

    def test_unattributed_and_nonforward_work_stays_in_denominator(self):
        e,m=fixture();e.append(dict(name='unattributed',ph='X',pid=9,tid=3,ts=800,dur=9,args={'Task Type':'EVENT WAIT'}))
        e.extend([dict(name='torch_to_npu',ph='s',cat='async_npu',id=20,pid=1,tid=1,ts=500),dict(name='torch_to_npu',ph='f',cat='async_npu',id=20,pid=9,tid=2,ts=550),dict(name='head',ph='X',pid=9,tid=2,ts=550,dur=2,args={'Task Type':'KERNEL_AIVEC'})])
        r=join(e,m,PIN);self.assertEqual(r['total_device_work']['tasks'],5);self.assertEqual(r['unattributed_tasks']['tasks'],1);self.assertEqual(r['correlated_outside_forward']['tasks'],1)

    def scorer(self,fail=False):
        calls=[];sentinel=object()
        def forward(*args,**kw):
            calls.append((args,kw))
            if fail:raise RuntimeError('actual model failed')
            return sentinel
        target=SimpleNamespace(forward=forward)
        def batch(b,w,out,right_pad=True):return target.forward(out,shape=(len(b),w))
        return SimpleNamespace(lm=SimpleNamespace(model=target),_score_flat_batch=batch),calls,sentinel

    def test_real_boundary_one_call_and_return_identity_no_extra_work(self):
        sc,calls,sentinel=self.scorer();names=[]
        @contextlib.contextmanager
        def record(name):names.append(name);yield
        n=NamedForward(sc,PIN,1,record);original=sc.lm.model.forward
        rows=[{'id':'q'}];batch=[(0,0,[1,2,3],1)]
        with n:
            for phase in PHASES:
                with n.scope(phase,CELL,rows):
                    for _ in range(3):self.assertIs(sc._score_flat_batch(batch,3,sentinel),sentinel)
        self.assertIs(sc.lm.model.forward,original);self.assertEqual(len(calls),21);self.assertEqual(len(names),3)
        manifest=n.manifest();self.assertEqual(manifest['total_forwards'],21);self.assertEqual(manifest['records'][0]['members'][0]['input_ids'],[1,2,3])

    def test_exception_restores_model_scorer_and_context(self):
        sc,_,_=self.scorer(fail=True);old=sc.lm.model.forward;oldbatch=sc._score_flat_batch;n=NamedForward(sc,PIN,1,lambda _:contextlib.nullcontext())
        with self.assertRaisesRegex(RuntimeError,'model failed'):
            with n:
                with n.scope('trace',CELL,[{'id':'q'}]):sc._score_flat_batch([(0,0,[1],1)],1,{})
        self.assertIs(sc.lm.model.forward,old);self.assertIs(sc._score_flat_batch,oldbatch);self.assertIsNone(n.active);self.assertEqual(n.records[0]['status'],'entered')
        with self.assertRaises(ValueError):n.manifest()

    def test_unscoped_forward_refused(self):
        sc,_,_=self.scorer();n=NamedForward(sc,PIN,1,lambda _:contextlib.nullcontext())
        with n:
            with self.assertRaises(ValueError):sc.lm.model.forward()

    def test_cpu_command_excludes_host_driver_and_devices(self):
        d=dict(container='named',environment={},mounts=[dict(source=x,destination=x,readonly=False) for x in ['/raw','/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']],out='/raw',image_sha256='sha256:x',runtime={'path':'/runtime'})
        c=H.cpu_command(d,'/plan','hash',1)
        self.assertNotIn('--device',c);self.assertNotIn('--privileged',c);self.assertNotIn('--rm',c)
        self.assertFalse(any('Ascend/driver' in x or '/usr/local/sbin' in x or '/etc/ascend_install.info' in x for x in c))
        self.assertIn('type=bind,src=/raw,dst=/raw,readonly',c)

if __name__=='__main__':unittest.main()
