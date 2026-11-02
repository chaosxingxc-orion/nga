import copy
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
import numpy as np
from tools import bev_native_dev_probe as P
from tools import bev_native_runtime as R
from tools.test_bev_native_runtime import Tok


class NativeDevProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=R.reference();cls.engine=P.upstream_engine(R.UPSTREAM/'anyjev/tacit.py',R.PINS['tacit.py'],cls.ref)
    def fixture(self):
        import torch
        class T(Tok):
            padding_side='left'
            def __call__(self,texts,**kw):
                class Enc(dict):
                    def to(self,device):return self
                ids=[self.encode(t) for t in texts]
                return Enc(input_ids=torch.tensor(ids),attention_mask=torch.ones((len(ids),len(ids[0])),dtype=torch.long))
        class Model:
            device='cpu'
            def __call__(self,**kw):return types.SimpleNamespace(logits=torch.arange(128,dtype=torch.float32).reshape(1,1,-1))
        tok=T();item=R.prepare_request(dict(i=0,qid='q',state='s',question='Q?',options=['x','y'],kind='choice'),tok,self.ref)
        return Model(),tok,item
    def test_actual_upstream_and_adapter_operands_exact(self):
        model,tok,item=self.fixture();vals=[P.collect_one(model,tok,item,R,self.ref,self.engine,'a'*64,v) for v in ['reference','reference_repeat','adapter']]
        for value in vals[1:]:P.compare_operands(vals[0][0],value[0],vals[0][1],value[1])
        self.assertEqual(vals[2][1]['forwards'],1)
    def test_raw_difference_rejects_even_same_decision(self):
        model,tok,item=self.fixture();a,r=P.collect_one(model,tok,item,R,self.ref,self.engine,'a'*64,'adapter');b=copy.deepcopy(a);b['logits'][0,2]+=0.1
        with self.assertRaisesRegex(ValueError,'logits differs'):P.compare_operands(a,b,r,r)
    def test_input_mutation_before_forward_rejects(self):
        model,tok,item=self.fixture();item['input_ids'][-1]+=1
        with self.assertRaisesRegex(ValueError,'tokenizer'):P.collect_one(model,tok,item,R,self.ref,self.engine,'a'*64,'reference')
    def test_gold_population_rejects(self):
        model,tok,item=self.fixture();rows=[]
        for kind in ['choice','noul','score']:
            for i in range(24):rows.append(dict(item,i=len(rows),kind=kind))
        P.validate_items(rows,R,list(map(R.digest,rows)))
        rows[0]['gold']=0
        with self.assertRaisesRegex(ValueError,'gold/foreign'):P.validate_items(rows,R,list(map(R.digest,rows)))
    def test_reordered_population_rejects(self):
        model,tok,item=self.fixture();rows=[dict(item,i=i,kind=['choice','noul','score'][i//24]) for i in range(72)];pins=list(map(R.digest,rows));rows.reverse()
        with self.assertRaisesRegex(ValueError,'order'):P.validate_items(rows,R,pins)
    def test_immutable_operands_saved_before_gate(self):
        model,tok,item=self.fixture();a,r=P.collect_one(model,tok,item,R,self.ref,self.engine,'a'*64,'reference')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'operand';pins=P.persist_operand(root,a,r)
            for name,h in pins.items():self.assertEqual(P.sha(root/name),h)
            with np.load(root/'operands.npz') as z:self.assertTrue(np.array_equal(z['logits'],a['logits']))
            with self.assertRaises(FileExistsError):P.persist_operand(root,a,r)
    def test_upstream_pin_and_extra_forward_input_reject(self):
        with self.assertRaises(ValueError):P.upstream_engine(R.UPSTREAM/'anyjev/tacit.py','0'*64,self.ref)
        model,_,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'unregistered'):P.CaptureModel(model)(position_ids=None)


if __name__=='__main__':unittest.main()
