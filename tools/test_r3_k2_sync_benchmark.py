"""Exercise actual benchmark orchestration with torch CPU and synthetic trainer.

No model, dataset, Docker or NPU access. Timing is a deterministic fixture, so
these tests establish orchestration only and never real performance evidence.
"""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
import r3_k2_sync_benchmark as B

class Benchmark(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.out=self.root/'results';self.train=self.root/'train.jsonl';self.train.write_text('synthetic')
        self.trainer=self.root/'train_r3.py';self.trainer.write_text('# fixture')
        self.candidate=self.root/'candidate.py'
        self.candidate.write_text('def step_loss(*a, **kw):\n    return synthetic_loss(*a, **kw)\n')
        self.transform=self.root/'transform.py';self.transform.write_text('# fixture')
        self.files={str(p):B.sha(p) for p in (self.train,self.trainer,self.candidate,self.transform,Path(B.__file__).resolve())}
        self.plan={'schema':'r3-k2-deferred-sync-benchmark-v1','test_read':False,'scientific_acceptance':False,
            'files':self.files,'trainer':str(self.trainer),'candidate':str(self.candidate),'transform':str(self.transform),
            'model':str(self.root/'model'),'out':str(self.out),'protocol':{'seed':2,'warmup_pairs':3,'measured_pairs':10,
                'min_measured_seconds':60,'exact_loss_and_gradients':True,'minimum_speedup':1.05,'chips':1}}
        self.path=self.root/'plan.json';self.path.write_text(json.dumps(self.plan));self.pin=B.sha(self.path)
        self.weight=torch.nn.Parameter(torch.tensor([.2,.4]));self.calls=[]
        def loss(torch,core,tok,units,*a,**kw):
            self.calls.append(units[0]);value=(self.weight*torch.tensor([1.,2.])).sum();value.backward()
            return float(value.detach()),{'tokens':20,'rows':10,'resp_tokens':0}
        def zero(**kw):self.weight.grad=None
        pm=SimpleNamespace(to=lambda d:None,train=lambda:None,zero_grad=zero,base_model=SimpleNamespace(model=object()))
        self.T=SimpleNamespace(TRAIN_FILE=str(self.train),file_sha256=B.sha,
            parse_args=lambda a:SimpleNamespace(model_path='synthetic',device='cpu'),
            Data=lambda a:SimpleNamespace(step_units=lambda step:(0,[step]*10)),
            build_model=lambda a,t:(pm,[('w',self.weight)],186),seed_step=lambda *a:None,
            step_loss=loss,synthetic_loss=loss)
        self.clock=iter(range(0,10000,10))
        def loader(path,name):
            if str(path)==str(self.transform):return SimpleNamespace(transform=lambda raw:self.candidate.read_bytes())
            return self.T
        self.loader=loader
        self.npu=SimpleNamespace(synchronize=lambda:None,reset_peak_memory_stats=lambda:None,max_memory_reserved=lambda:2*1024**3)

    def execute(self):
        transformer=SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda p:SimpleNamespace(pad_token_id=0)))
        with patch.object(B,'source',side_effect=self.loader),patch.object(B.time,'perf_counter',side_effect=lambda:next(self.clock)), \
             patch.object(torch,'npu',self.npu,create=True),patch.dict(sys.modules,{'torch_npu':SimpleNamespace(),'transformers':transformer}):
            return B.run(self.path,self.pin)

    def test_full_pair_loop_warmup_counts_and_per_chip_metrics(self):
        result=self.execute()
        self.assertEqual(len(self.calls),28)
        self.assertEqual(len(result['rows']),13)
        self.assertEqual(result['seconds'],{'reference':100,'candidate':100})
        self.assertEqual(result['speedup'],1);self.assertFalse(result['engineering_speed_candidate'])
        self.assertTrue(result['exact_loss_and_gradients'])
        for row in result['performance'].values():
            self.assertEqual(row,{'questions_per_second_per_chip':1,'tokens_per_second_per_chip':2,
                                  'reserved_gib_peak':2,'chips':1})
        self.assertFalse(result['test_read']);self.assertFalse(result['scientific_acceptance'])
        self.assertEqual(B.sha(self.path),self.pin)
        self.assertEqual(json.loads((self.out/'heartbeat.json').read_text())['completed_pairs'],13)
        with self.assertRaisesRegex(ValueError,'fresh benchmark'):self.execute()

    def test_changed_gradient_fails_without_result(self):
        original=self.T.synthetic_loss
        def changed(*a,**kw):
            result=original(*a,**kw);self.weight.grad[0]+=1;return result
        self.T.synthetic_loss=changed
        with self.assertRaisesRegex(ValueError,'candidate changed'):self.execute()
        self.assertFalse((self.out/'RESULT.json').exists())

if __name__=='__main__':unittest.main()
