import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_config_panel as C, bev_native_config_panel_host as H, bev_native_config_panel_consume as U


class PanelConfig(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        def ref(name,raw='{}'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw);return {'path':str(p),'sha256':C.sha(p)}
        self.ref=ref;modules={}
        for name in C.MODULES:
            if name=='runtime': p=Path(C.__file__).resolve();modules[name]={'path':str(p),'sha256':C.sha(p)}
            elif name=='consumer':
                p=Path(C.__file__).resolve().with_name('bev_native_config_panel_consume.py');modules[name]={'path':str(p),'sha256':C.sha(p)}
            elif name=='loader':modules[name]=ref('loader.py',"ENV={}\nIMAGE='sha256:'+('a'*64)\n")
            else:modules[name]=ref(name+'.py','')
        weights=ref('model/weights','weights');mf={weights['path']:weights['sha256']}
        pop={k:ref(k+'.json') for k in ('requests','items','gold','source','contract')}
        pop.update(count=46320,source_rows=24386,semantic_duplicates=9,kinds={'choice':18808,'yes_no':17572,'score':9940},ordered_inputs_sha256='a'*64,contract_sha256='b'*64,protocol_binding_sha256='c'*64)
        up={n:ref('up/anyjev/'+n,'') for n in ('question.py','readout.py','tacit.py')};policy=ref('policy.json')
        refs=[*modules.values(),*up.values(),policy,*[pop[k] for k in ('requests','items','gold','source','contract')]]
        self.c=dict(schema='native-panel-config-v2',run_id='task1',output=str(self.root/'task1/output'),container='task1',host_name='host',host_environment={},host_python=str(Path(sys.executable).resolve()),cpu_python=str(Path(sys.executable).resolve()),cpu_environment={'TORCH_DEVICE_BACKEND_AUTOLOAD':'0'},model=dict(path=str(self.root/'model'),files=mf,manifest_sha256=C.digest(mf),family='qwen3.5_decoder',name='model-one',kind='fixed_base'),population=pop,protocol=dict(id='native-full-label-panel-v2',family='qwen3.5_decoder',max_length=8192,batch_size=1,dtype='float32',hf32=False,vocabulary=248320,adapter='transformers_full_labels'),modules=modules,upstream={'root':str(self.root/'up'),'files':up},resources={'chip':2,'allocation':str(self.root/'allocation.json'),'policy':policy},image='sha256:'+'a'*64,environment={},files={r['path']:r['sha256'] for r in refs},scope='public_fixed_base_test',test_read=True,scientific_acceptance=False,candidate_test_authority=False,candidate_selection_allowed=False,poll_seconds=600)
    def build(self,c=None):
        c=c or self.c;p=self.root/(c['run_id']+'.json');p.write_text(json.dumps(c));plan=Path(c['output']).parent/'PLAN.json'
        with patch.object(C,'validate_population') as validation:
            d=C.build(str(p),C.sha(p),str(plan));validation.assert_called_once()
        return plan,d
    def test_config_only_second_model_same_modules(self):
        p,a=self.build();b=copy.deepcopy(self.c);w=self.ref('second/weights','different');b['model'].update(path=str(self.root/'second'),files={w['path']:w['sha256']},name='second',manifest_sha256=C.digest({w['path']:w['sha256']}));b.update(run_id='task2',container='task2',output=str(self.root/'task2/output'));b['resources']['chip']=6
        q,second=self.build(b);C.verify(str(p),C.sha(p));C.verify(str(q),C.sha(q));self.assertEqual(a['modules'],second['modules']);self.assertNotEqual(a['model_sha256'],second['model_sha256'])
        ca=H.command({**a,'runtime':a['modules']['runtime'],'image_sha256':a['image']},str(p),C.sha(p),1);cb=H.command({**second,'runtime':second['modules']['runtime'],'image_sha256':second['image']},str(q),C.sha(q),1)
        self.assertIn('/dev/davinci2',ca);self.assertIn('/dev/davinci6',cb);self.assertNotIn('--rm',cb)
    def test_invalid_schema_types_and_scope_reject(self):
        for key,value in [('schema','native-experiment-config-v1'),('test_read',1),('candidate_test_authority',True),('poll_seconds',True)]:
            bad=copy.deepcopy(self.c);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):C.config_validate(bad)
        for path,value in [(('resources','chip'),False),(('model','kind'),'trained_adapter'),(('protocol','hf32'),0),(('population','count'),46319),(('population','semantic_duplicates'),True)]:
            bad=copy.deepcopy(self.c);bad[path[0]][path[1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):C.config_validate(bad)
    def test_inference_mount_excludes_gold_and_source(self):
        p,d=self.build();paths={x['source'] for x in d['mounts']}
        for k in ('gold','items','source','contract'):self.assertNotIn(d['population'][k]['path'],paths)
        self.assertIn(d['population']['requests']['path'],paths)
    def test_cpu_only_ancestor_mount_rejected(self):
        p,d=self.build()
        for kind in ('items','gold','source','contract'):
            for mount in d['mounts']:
                for path in (Path(mount['source']),Path(mount['source'])/'cpu-only.json'):
                    bad=copy.deepcopy(d);bad['population'][kind]['path']=str(path)
                    with self.subTest(kind=kind,path=str(path)):
                        try:actual=C.mounts(bad,p)
                        except ValueError as error:self.assertIn('CPU-only path',str(error))
                        else:self.assertFalse(any(path.is_relative_to(m['source']) for m in actual))

    def test_plan_projection_and_sources_reject(self):
        p,d=self.build();bad=dict(d,chip=3);p.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,'resource projection'):C.verify(str(p),C.sha(p))
        p.write_text(json.dumps(d));Path(d['population']['requests']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'source changed'):C.verify(str(p),C.sha(p))
    def test_startup_failure_terminal_without_model_import(self):
        p,d=self.build();d['schema']='foreign';p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):C.run(str(p),C.sha(p),1)
        e=C.read(Path(d['out'])/'attempts/1/EXIT.json');self.assertEqual(e['exit_code'],1);self.assertIs(e['test_read'],True)
    def test_cpu_handoff_requires_successful_release(self):
        p,d=self.build();h=Path(d['out'])/'host_attempts/1';h.mkdir(parents=True)
        claim={'run':d['run'],'chip':d['chip'],'schema':'r3-resource-claim-v1'};C.put(h/'CLAIM.json',claim);C.put(h/'EXIT.json',{'exit_code':0,'runner_terminal_matches':True,'container_id':'a'});C.put(h/'RELEASE.json',{'claim_sha256':C.sha(h/'CLAIM.json'),'container_id':'a','run':d['run'],'schema':'r3-resource-release-v1','exit_code':0,'scientific_acceptance':False,'chip':d['chip']})
        fake=types.SimpleNamespace(pid=42)
        with patch.object(C.subprocess,'Popen',return_value=fake) as spawn:C.start_cpu(d,str(p),C.sha(p),1)
        args,kwargs=spawn.call_args;self.assertTrue(kwargs['start_new_session']);self.assertEqual(kwargs['env']['TORCH_DEVICE_BACKEND_AUTOLOAD'],'0');self.assertNotIn('docker',args[0]);self.assertTrue((Path(d['out'])/'cpu/1/SERVICE.json').exists())
        with self.assertRaises(FileExistsError):C.start_cpu(d,str(p),C.sha(p),1)
        C.put(h/'EXIT.json',{'exit_code':False,'runner_terminal_matches':True,'container_id':'a'})
        with self.assertRaisesRegex(ValueError,'host not successful'):C.start_cpu(d,str(p),C.sha(p),1)
    def test_long_dev_gate_not_a_config_boolean(self):
        p,d=self.build();g=self.ref('gate.json',json.dumps({'verdict':'PASS'}));r={'long_dev_acceptance':g,'cpu_command':C.cpu_command(d,str(p),C.sha(p),1)}
        with self.assertRaisesRegex(ValueError,'gate differs'):C.admission(d,r,str(p),C.sha(p),1)

    def test_cpu_handoff_failure_preserves_npu_truth(self):
        p,d=self.build();h=Path(d['out'])/'host_attempts/1';h.mkdir(parents=True)
        C.put(h/'EXIT.json',{'exit_code':0,'runner_terminal_matches':True});C.put(h/'RELEASE.json',{'exit_code':0})
        before={n:(h/n).read_bytes() for n in ('EXIT.json','RELEASE.json')}
        args=types.SimpleNamespace(plan=str(p),sha256=C.sha(p),attempt=1)
        fake=types.SimpleNamespace(start_cpu=lambda *a:(_ for _ in ()).throw(RuntimeError('spawn failed')))
        with patch.object(H,'module',return_value=fake):H.handoff_cpu(d,args)
        self.assertEqual(before,{n:(h/n).read_bytes() for n in before})
        error=C.read(Path(d['out'])/'cpu/HANDOFF-ERROR.json');self.assertEqual(error['status'],'needs_cpu_reconciliation')
        self.assertEqual(error['plan_sha256'],C.sha(p));self.assertEqual(error['exit_code'],1)

    def test_cpu_handoff_diagnostic_failures_preserve_npu_truth(self):
        p,d=self.build();h=Path(d['out'])/'host_attempts/1';h.mkdir(parents=True)
        C.put(h/'EXIT.json',{'exit_code':0,'runner_terminal_matches':True});C.put(h/'RELEASE.json',{'exit_code':0})
        before={n:(h/n).read_bytes() for n in ('EXIT.json','RELEASE.json')}
        fake=types.SimpleNamespace(start_cpu=lambda *a:(_ for _ in ()).throw(FileNotFoundError('cpu missing')))
        argv=['host','supervise','--plan',str(p),'--sha256',C.sha(p),'--review','r','--review-sha256','rpin']
        original_put=H.put
        def failed_journal(path,value):
            if Path(path).name=='HANDOFF-ERROR.json':raise OSError('journal unavailable')
            return original_put(path,value)
        for diagnostic_failure in (False,True):
            with self.subTest(diagnostic_failure=diagnostic_failure),patch.object(sys,'argv',argv),patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H.socket,'gethostname',return_value=d['host_name']),patch.object(H,'supervise',side_effect=lambda args:H.handoff_cpu(d,args)),patch.object(H,'module',return_value=fake),patch.object(H,'put',side_effect=failed_journal),patch('builtins.print',side_effect=OSError('stream unavailable') if diagnostic_failure else None):
                H.main()
            self.assertEqual(before,{n:(h/n).read_bytes() for n in before})
        args=types.SimpleNamespace(plan=str(p),sha256=C.sha(p),attempt=1)
        with patch.object(H,'module',return_value=fake),patch.object(Path,'mkdir',side_effect=OSError('directory unavailable')),patch('builtins.print'):
            H.handoff_cpu(d,args)
        self.assertEqual(before,{n:(h/n).read_bytes() for n in before})

    def test_consumer_rejects_foreign_completion_identity(self):
        p,d=self.build();h=Path(d['out'])/'host_attempts/1';a=Path(d['out'])/'attempts/1';h.mkdir(parents=True);a.mkdir(parents=True);pin=C.sha(p);cid='a'*64
        C.put(h/'CLAIM.json',{'run':d['run'],'chip':d['chip'],'schema':'r3-resource-claim-v1'})
        C.put(a/'EXIT.json',{'exit_code':0,'attempt':1,'plan_sha256':pin,'test_read':True,'scientific_acceptance':False})
        C.put(h/'EXIT.json',{'exit_code':0,'container_exit_code':0,'runner_terminal_matches':True,'plan_sha256':pin,'attempt':1,'scientific_acceptance':False,'container_id':cid})
        cmd=['image','run'];C.put(h/'LAUNCH_SPEC.json',{'plan_sha256':pin,'command':cmd});C.put(h/'LAUNCH_RECEIPT.json',{'plan_sha256':pin,'attempt':1,'container_id':cid,'command':['run']})
        C.put(h/'RELEASE.json',{'schema':'r3-resource-release-v1','run':d['run'],'chip':d['chip'],'claim_sha256':C.sha(h/'CLAIM.json'),'container_id':cid,'exit_code':0,'scientific_acceptance':False,'container':'task1-a1'})
        d=dict(d,image='image');report={'schema':'bev-native-panel-completion-v1','attempt':1,'plan_sha256':pin,'scientific_acceptance':False,'model_sha256':d['model_sha256'],'contract_sha256':d['population']['contract_sha256'],'ordered_inputs_sha256':d['population']['ordered_inputs_sha256'],'adaptive':'NOT_EVALUATED','forwards_per_new_item':1}
        fake=types.SimpleNamespace(command=lambda *x:cmd)
        with patch.object(U.C,'module',return_value=fake):
            C.put(a/'report.json',report);self.assertEqual(U.lifecycle(d,pin,1),report)
            for key,value in [('schema','foreign'),('attempt',True),('plan_sha256','foreign'),('scientific_acceptance',True),('model_sha256','foreign')]:
                C.put(a/'report.json',dict(report,**{key:value}))
                with self.subTest(key=key),self.assertRaises(ValueError):U.lifecycle(d,pin,1)

if __name__=='__main__':unittest.main()
