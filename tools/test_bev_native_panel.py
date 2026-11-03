import copy,json,tempfile,unittest
from pathlib import Path
from tools import bev_native_panel_runner as X, bev_native_runtime as N, bev_native_protocol as P, bev_native_panel_consume as C

class Panel(unittest.TestCase):
    def test_fixed_base_config_identity(self):
        for mirror in ('/mnt/cephfs/xingchao/models/jev','/mnt/cephfs/xingchao/omni/models/jev'):
            for size in ('0.8B','2B','4B'):
                self.assertEqual(X.fixed_base_name(mirror+'/Qwen__Qwen3.5-'+size+'-Base'),'Qwen3.5-'+size+'-Base')
        for path in ('/tmp/Qwen__Qwen3.5-2B-Base','/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-2B','/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-9B-Base','/mnt/cephfs/xingchao/models/jev/../jev/Qwen__Qwen3.5-2B-Base'):
            with self.subTest(path=path),self.assertRaises(ValueError):X.fixed_base_name(path)
    def fixture(self):
        import numpy as np
        items=[dict(i=i,qid='same',y=0,state='same',question='q',options=['a','b'],kind='choice') for i in range(2)]
        req=[dict(schema='bev-native-input-v1',i=i,qid='same',request_sha256=P.request_hash(it),input_ids=[5,6],rendered_prompt='xx',labels=['A','B'],label_ids=[32,33],options=['a','b'],kind='choice') for i,it in enumerate(items)]
        contract=P.make_contract(items,source_sha256='a'*64,model_sha256='b'*64,runtime_protocol_sha256='c'*64)
        d=dict(max_length=8192,model_sha256='b'*64,contract_sha256=P.sha256_value(contract),ordered_inputs_sha256=N.digest(req))
        z=np.zeros(248320,dtype=np.float32);z[32]=2
        def collect(item):return N.read_logits(item,z,mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_sha256=N.digest(item))
        gold=[dict(i=it['i'],qid=it['qid'],y=it['y'],request_sha256=P.request_hash(it)) for it in items]
        return items,req,contract,d,collect,gold
    def test_producer_consumer_resume_and_duplicates(self):
        items,req,contract,d,collect,gold=self.fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=X.execute(d,N,req,root,1,collect,lambda:{})
            b=X.execute(d,N,req,root,2,lambda i:self.fail('recomputed'),lambda:{})
            self.assertEqual((a['computed'],b['reused']),(2,2));self.assertEqual(a['receipts_sha256'],b['receipts_sha256'])
            pred=[X.load_item(root/'items'/f'{i:06d}',r,d,N) for i,r in enumerate(req)]
            result=C.join(items,req,gold,pred,contract,P,N);self.assertEqual(result['one_forward']['accuracy'],1);self.assertEqual(result['adaptive'],'NOT_EVALUATED')
    def test_join_attacks(self):
        for attack in ('reorder','missing','duplicate','changed_input','bool_gold','bool_index','changed_contract','changed_model'):
            with self.subTest(attack=attack):
                items,req,contract,d,collect,gold=self.fixture();pred=[collect(r) for r in req]
                if attack=='reorder':pred.reverse()
                elif attack=='missing':pred.pop()
                elif attack=='duplicate':pred[1]=pred[0]
                elif attack=='changed_input':items[0]['state']='changed'
                elif attack=='bool_gold':gold[0]['y']=False
                elif attack=='bool_index':pred[0]['index']=False
                elif attack=='changed_contract':contract['tau']=0.2
                elif attack=='changed_model':contract['model_sha256']='d'*64
                with self.assertRaises(ValueError):C.join(items,req,gold,pred,contract,P,N)
    def test_resigned_record_attacks(self):
        for attack in ('model','contract','bool_forwards','bool_label','bool_index','input','arithmetic'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as td:
                items,req,contract,d,collect,gold=self.fixture();root=Path(td);X.execute(d,N,req,root,1,collect,lambda:{})
                dest=root/'items/000000';r=X.read(dest/'record.json')
                if attack=='model':r['model_sha256']='d'*64
                elif attack=='contract':r['contract_sha256']='d'*64
                elif attack=='bool_forwards':r['forwards']=True
                elif attack=='bool_label':r['prediction']['label_ids'][0]=True
                elif attack=='bool_index':r['prediction']['index']=False
                elif attack=='input':r['prediction']['input_sha256']='d'*64
                else:r['prediction']['restricted_logprobs'][0]+=1
                X.write(dest/'record.json',r);X.write(dest/'COMMITTED.json',{'record.json':X.sha(dest/'record.json')})
                with self.assertRaises(ValueError):X.execute(d,N,req,root,2,collect,lambda:{})
    def test_partial_missing_and_extra(self):
        items,req,contract,d,collect,gold=self.fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'items/000000').mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):X.execute(d,N,req,root,1,collect,lambda:{})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'items/999999').mkdir(parents=True)
            with self.assertRaises(ValueError):X.execute(d,N,req,root,1,collect,lambda:{})
    def test_failure_resume_and_model_change(self):
        items,req,contract,d,collect,gold=self.fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            def fail(item):
                if item['i']==1:raise RuntimeError('interrupted')
                return collect(item)
            with self.assertRaises(RuntimeError):X.execute(d,N,req,root,1,fail,lambda:{})
            result=X.execute(d,N,req,root,2,collect,lambda:{})
            self.assertEqual(result['reused'],1)
            with self.assertRaises(ValueError):X.execute(dict(d,model_sha256='e'*64),N,req,root,3,collect,lambda:{})
    def test_lifecycle_fail_closed(self):
        from tools import bev_native_panel_host as H
        from unittest.mock import patch
        items,req,contract,d,collect,gold=self.fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'output';a=root/'attempts/1';h=root/'host_attempts/1';a.mkdir(parents=True);h.mkdir(parents=True)
            d.update(out=str(root),container='nga-native-panel-fixture',run='fixture',chip=7,environment={},mounts=[],image_sha256='sha256:x',runtime={'path':'/runner'},host={})
            pp=root.parent/'HOST-PLAN.json';X.write(pp,d);pin=X.sha(pp);cmd=H.command(d,str(pp),pin,1)
            X.write(a/'EXIT.json',dict(exit_code=0,attempt=1,plan_sha256=pin,scientific_acceptance=False));X.write(a/'report.json',dict(complete=True,schema='bev-native-panel-completion-v1',scientific_acceptance=False,adaptive='NOT_EVALUATED'))
            X.write(h/'EXIT.json',dict(exit_code=0,container_exit_code=0,runner_terminal_matches=True,container_id='c'*64,scientific_acceptance=False))
            X.write(h/'CLAIM.json',dict(run='fixture',chip=7));X.write(h/'RELEASE.json',dict(schema='r3-resource-release-v1',run='fixture',chip=7,container_id='c'*64,claim_sha256=X.sha(h/'CLAIM.json'),exit_code=0,scientific_acceptance=False,container=d['container']+'-a1'))
            X.write(h/'LAUNCH_SPEC.json',dict(plan_sha256=pin,command=cmd));X.write(h/'LAUNCH_RECEIPT.json',dict(plan_sha256=pin,container_id='c'*64,command=cmd[cmd.index('sha256:x')+1:]))
            with patch.object(X,'module',return_value=H):
                self.assertTrue(C.lifecycle(d,pin,1,X)['complete'])
                r=X.read(h/'RELEASE.json');r['claim_sha256']='f'*64;X.write(h/'RELEASE.json',r)
                with self.assertRaises(ValueError):C.lifecycle(d,pin,1,X)
    def test_long_boundaries(self):
        _,req,_,_,_,_=self.fixture()
        for n in (4097,5296,8192):
            r=dict(req[0],input_ids=[5]*n);X.item_check(r,0,8192)
        with self.assertRaises(ValueError):X.item_check(dict(req[0],input_ids=[5]*8193),0,8192)
    def test_lifecycle_individual_attacks(self):
        from tools import bev_native_panel_host as H
        from unittest.mock import patch
        mutations=[('runtime','attempt',True),('runtime','scientific_acceptance',True),('runtime','exit_code',False),('runtime','plan_sha256','foreign'),('host','container_exit_code',False),('host','scientific_acceptance',True),('host','runner_terminal_matches',1),('release','exit_code',1),('release','exit_code',False),('release','chip',True),('release','run','foreign'),('release','container','foreign'),('release','scientific_acceptance',True),('claim','chip',True),('report','scientific_acceptance',True)]
        for kind,key,value in mutations:
            with self.subTest(kind=kind,key=key,value=value),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'output';a=root/'attempts/1';h=root/'host_attempts/1';a.mkdir(parents=True);h.mkdir(parents=True)
                d=dict(out=str(root),container='nga-native-panel-fixture',run='fixture',chip=7,environment={},mounts=[],image_sha256='sha256:x',runtime={'path':'/runner'},host={})
                pp=root.parent/'HOST-PLAN.json';X.write(pp,d);pin=X.sha(pp);cmd=H.command(d,str(pp),pin,1)
                docs={'runtime':(a/'EXIT.json',dict(exit_code=0,attempt=1,plan_sha256=pin,scientific_acceptance=False)), 'host':(h/'EXIT.json',dict(exit_code=0,container_exit_code=0,runner_terminal_matches=True,container_id='c'*64,scientific_acceptance=False)), 'claim':(h/'CLAIM.json',dict(run='fixture',chip=7)), 'report':(a/'report.json',dict(schema='bev-native-panel-completion-v1',scientific_acceptance=False,adaptive='NOT_EVALUATED'))}
                for p,v in docs.values():X.write(p,v)
                docs['release']=(h/'RELEASE.json',dict(schema='r3-resource-release-v1',run='fixture',chip=7,container_id='c'*64,claim_sha256=X.sha(h/'CLAIM.json'),exit_code=0,scientific_acceptance=False,container=d['container']+'-a1'))
                X.write(*docs['release']);X.write(h/'LAUNCH_SPEC.json',dict(plan_sha256=pin,command=cmd));X.write(h/'LAUNCH_RECEIPT.json',dict(plan_sha256=pin,container_id='c'*64,command=cmd[cmd.index('sha256:x')+1:]))
                with patch.object(X,'module',return_value=H):
                    C.lifecycle(d,pin,1,X)
                    p,v=docs[kind];v[key]=value;X.write(p,v)
                    with self.assertRaises(ValueError):C.lifecycle(d,pin,1,X)
    def test_cpu_worker_terminal_and_duplicate(self):
        from unittest.mock import patch
        import types
        for fails in (False,True):
            with self.subTest(fails=fails),tempfile.TemporaryDirectory() as td:
                root=Path(td);h=root/'output/cpu/1';h.mkdir(parents=True)
                v=types.SimpleNamespace(plan=str(root/'HOST-PLAN.json'),sha256='a'*64,cpu_plan=str(root/'CPU-PLAN.json'),cpu_sha256='b'*64,attempt=1,output=str(h/'summary.json'))
                with patch.object(C,'consume',side_effect=ValueError('bad') if fails else None,return_value={'n':2}):
                    if fails:
                        with self.assertRaises(ValueError):C.worker(v)
                    else:C.worker(v)
                e=X.read(h/'EXIT.json');self.assertEqual(e['exit_code'],int(fails));self.assertIs(e['scientific_acceptance'],False)
                with self.assertRaises(ValueError):C.worker(v)
    def test_cpu_start_requires_lifecycle_then_detaches_once(self):
        from tools import bev_native_panel_host as H
        from unittest.mock import patch,Mock
        import types
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);out=root/'output';out.mkdir();cp=root/'CPU-PLAN.json'
            X.write(cp,dict(python='/python',consumer={'path':'/consumer'}))
            d=dict(out=str(out));args=types.SimpleNamespace(plan=str(root/'HOST-PLAN.json'),sha256='a'*64,review='/review',review_sha256='b'*64,attempt=1)
            order=[];consumer=types.SimpleNamespace(lifecycle=lambda *a:order.append('lifecycle'))
            d['runtime']={'path':'runner'}
            with patch.object(H,'approval',side_effect=lambda *a:order.append('approval')),patch.object(H,'module',side_effect=[consumer,X,consumer,X]),patch.object(H.subprocess,'Popen',side_effect=lambda *a,**kw:(order.append(('spawn',kw['start_new_session'])),types.SimpleNamespace(pid=42))[1]) as spawn:
                H.start_cpu(args,d)
                self.assertEqual(order,['approval','lifecycle',('spawn',True)])
                self.assertIn('--worker',X.read(out/'cpu/1/SERVICE.json')['command'])
                with self.assertRaises(FileExistsError):H.start_cpu(args,d)
                self.assertEqual(spawn.call_count,1)
    def test_actual_runner_long_dev_interface(self):
        import torch,types,numpy as np
        from unittest.mock import patch
        from tools import bev_native_dev_probe as Probe
        class Tok:
            padding_side='left'
            def encode(self,text,**kw):return [5]*len(text)
            def __call__(self,texts,**kw):
                class Enc(dict):
                    def to(self,device):return self
                return Enc(input_ids=torch.tensor([[5]*len(t) for t in texts]),attention_mask=torch.ones((len(texts),len(texts[0])),dtype=torch.long))
        class Model:
            device='cpu'
            def __call__(self,**kw):return types.SimpleNamespace(logits=torch.arange(248320,dtype=torch.float32).reshape(1,1,-1))
        _,base,_,d,_,_=self.fixture();req=[dict(base[0],i=i,qid=str(i),input_ids=[5]*n,rendered_prompt='x'*n) for i,n in enumerate((4097,5296,8192))]
        fake=types.SimpleNamespace(__version__=torch.__version__,npu=types.SimpleNamespace(memory_reserved=lambda:0,max_memory_reserved=lambda:0))
        loader=types.SimpleNamespace(load_model=lambda p:(Model(),Tok(),fake,types.SimpleNamespace(__version__='test'),types.SimpleNamespace(__version__='test')))
        with tempfile.TemporaryDirectory() as td:
            d.update(out=td,scope='synthetic_long_dev',model='fixture',upstream_root=str(N.UPSTREAM),probe={},upstream_files={'tacit.py':{'path':str(N.UPSTREAM/'anyjev/tacit.py'),'sha256':N.PINS['tacit.py']}},ordered_inputs_sha256=N.digest(req))
            path=Path(td)/'plan.json';X.write(path,d)
            with patch.object(X,'verify',return_value=(d,loader,N,req)),patch.object(X,'module',return_value=Probe):X.run(path,X.sha(path),1)
            self.assertEqual(X.read(Path(td)/'attempts/1/EXIT.json')['exit_code'],0)
            self.assertEqual(len(list((Path(td)/'long_operands').glob('*/*/COMMITTED.json'))),9)
            self.assertEqual(X.read(Path(td)/'attempts/1/report.json')['forwards_per_new_item'],3)
    def test_host_review_scope_and_command(self):
        from tools import bev_native_panel_host as H
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'plan.json';r=root/'review.json'
            d=dict(container='nga-native-panel-test',chip=7,environment={'Z':'1','A':'2'},mounts=[],image_sha256='sha256:x',runtime={'path':'/runtime'},files={},test_read=False,scope='synthetic_long_dev')
            X.write(p,d);h=X.sha(p);cmd=H.command(d,str(p),h,1)
            self.assertNotIn('--rm',cmd);self.assertNotIn('-I',cmd);self.assertIn('-d',cmd)
            receipt=dict(verdict='PASS',approved_plan_sha256=h,activation_authorized=True,scientific_acceptance=False,test_read=False,candidate_test_authority=False,scope=d['scope'],attempts=[1],expected_commands={'1':cmd},hashes={str(p):h})
            X.write(r,receipt);H.approval(X.read(p),str(p),h,str(r),X.sha(r),1)
            receipt['scope']='public_fixed_base_test';X.write(r,receipt)
            with self.assertRaises(ValueError):H.approval(d,str(p),h,str(r),X.sha(r),1)
if __name__=='__main__':unittest.main()
