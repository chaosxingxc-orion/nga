import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_dev_runner as X
from tools import bev_native_dev_probe as P
from tools import bev_native_runtime as R
from tools.test_bev_native_dev_probe import NativeDevProbe

class Execution(unittest.TestCase):
    def fixture(self):
        NativeDevProbe.setUpClass();f=NativeDevProbe();m,t,i=f.fixture()
        rows=[i,dict(i,i=1,qid='q1')]
        def collect(item,v):return P.collect_one(m,t,item,R,f.ref,f.engine,'a'*64,v)
        return rows,collect
    def test_completion_resume(self):
        items,c=self.fixture()
        with tempfile.TemporaryDirectory() as d:
            a=X.execute(P,R,items,Path(d),'a'*64,1,c,lambda:{})
            self.assertEqual(a['completed_items'],6)
            b=X.execute(P,R,items,Path(d),'a'*64,2,lambda *a:self.fail('recomputed'),lambda:{})
            self.assertEqual(b['reused_items'],6)
    def test_failure_then_resume(self):
        items,c=self.fixture();calls=[]
        def fail(i,v):
            calls.append(1)
            if len(calls)==3:raise RuntimeError('network')
            return c(i,v)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):X.execute(P,R,items,Path(d),'a'*64,1,fail,lambda:{})
            a=X.execute(P,R,items,Path(d),'a'*64,2,c,lambda:{})
            self.assertEqual(a['reused_items'],2)
    def test_partial_rejected(self):
        items,c=self.fixture()
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'items/reference'/R.digest(items[0])).mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):X.execute(P,R,items,Path(d),'a'*64,2,c,lambda:{})
    def test_saved_generation_and_typed_tamper(self):
        items,c=self.fixture()
        for field,value in [('contract_sha256','b'*64),('index',999),('input_sha256','b'*64)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                root=Path(d);X.execute(P,R,items,root,'a'*64,1,c,lambda:{})
                dest=root/'items/reference'/R.digest(items[0]);v=X.read(dest/'result.json');v['prediction'][field]=value;X.write(dest/'result.json',v)
                rec=X.read(dest/'COMMITTED.json');rec['result.json']=X.sha(dest/'result.json');X.write(dest/'COMMITTED.json',rec)
                with self.assertRaises(ValueError):X.execute(P,R,items,root,'a'*64,2,c,lambda:{})
    def test_resigned_all_pass_type_mutations_rejected(self):
        import numpy as np
        items,c=self.fixture();items=items[:1]
        for attack in ('bool_forwards','bool_index','bool_i','bool_reasoning','float64_ids'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d:
                root=Path(d);X.execute(P,R,items,root,'a'*64,1,c,lambda:{})
                for phase in ('reference','reference_repeat','adapter'):
                    dest=root/'items'/phase/R.digest(items[0]);v=X.read(dest/'result.json')
                    if attack=='bool_forwards':v['forwards']=True
                    elif attack=='bool_index':
                        v['prediction']['index']=bool(v['prediction']['index'])
                        v['prediction']['first_index']=bool(v['prediction']['first_index'])
                    elif attack=='bool_i':v['prediction']['i']=False
                    elif attack=='bool_reasoning':v['prediction']['reasoning_tokens']=False
                    else:
                        with np.load(dest/'operands.npz',allow_pickle=False) as z:a={k:z[k] for k in z.files}
                        for k in ('input_ids','attention_mask'):a[k]=a[k].astype(np.float64)
                        np.savez(dest/'operands.npz',**a)
                    X.write(dest/'result.json',v)
                    X.write(dest/'COMMITTED.json',{n:X.sha(dest/n) for n in ('operands.npz','result.json')})
                with self.assertRaises(ValueError):X.execute(P,R,items,root,'a'*64,2,lambda *a:self.fail('recomputed'),lambda:{})
    def test_persisted_command_approval(self):
        from tools import bev_native_dev_host as H
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'plan.json';r=root/'review.json'
            d=dict(container='nga-native-dev-test',chip=7,environment=dict(Z='last',A='first'),mounts=[],image_sha256=X.IMAGE,runtime={'path':'/runner'},files={})
            X.write(p,d);pin=X.sha(p)
            receipt=dict(verdict='PASS',approved_plan_sha256=pin,activation_authorized=True,scientific_acceptance=False,test_read=False,attempts=[1],expected_commands={'1':H.command(d,str(p),pin,1)},hashes={str(p):pin})
            X.write(r,receipt)
            self.assertEqual(H.command(d,str(p),pin,1),H.command(X.read(p),str(p),pin,1))
            H.approval(X.read(p),str(p),pin,str(r),X.sha(r),1)
    def test_raw_difference_rejects(self):
        items,c=self.fixture()
        def bad(i,v):
            a,r=c(i,v)
            if v=='adapter':a['logits'][0,2]+=1
            return a,r
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):X.execute(P,R,items,Path(d),'a'*64,1,bad,lambda:{})
    def test_preload_failure_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plan';p.write_text(json.dumps({'out':d}))
            with patch.object(X,'verify',side_effect=ValueError('loader differs')):
                with self.assertRaises(ValueError):X.run(p,'a'*64,1)
            self.assertEqual(X.read(Path(d)/'attempts/1/EXIT.json')['exit_code'],1)
    def test_command_retained_single_chip(self):
        from tools import bev_native_dev_host as H
        d=dict(container='nga-native-dev-test',chip=7,environment=X.ENV,mounts=[],image_sha256=X.IMAGE,runtime={'path':'/runner'})
        cmd=H.command(d,'/plan','a'*64,1)
        self.assertIn('-d',cmd);self.assertNotIn('--rm',cmd);self.assertIn('/dev/davinci7',cmd);self.assertNotIn('-I',cmd)
if __name__=='__main__':unittest.main()
