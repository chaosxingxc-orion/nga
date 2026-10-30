import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
import torch
from openjev_candidate_chunks import candidate_chunks


class Chunks(unittest.TestCase):
    def model(self):
        class Backbone(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.calls=[]
            def forward(self, **kw):
                self.calls.append((kw['input_ids'].clone(),kw['attention_mask'].clone()))
                # Padding-position-sensitive output catches local repadding.
                z=kw['input_ids']*kw['attention_mask']+torch.arange(kw['input_ids'].shape[1])
                return SimpleNamespace(last_hidden_state=z.unsqueeze(-1))
        return Backbone()
    def test_order_masks_global_padding_and_tail_are_preserved(self):
        b=self.model(); ids=torch.arange(35).reshape(5,7);mask=torch.tensor([[1]*n+[0]*(7-n) for n in [7,2,5,1,6]])
        kw=dict(input_ids=ids,attention_mask=mask,use_cache=False,return_dict=True)
        expected=b(**kw).last_hidden_state;b.calls=[];old=b.forward
        with candidate_chunks(b,2): actual=b(**kw).last_hidden_state
        self.assertTrue(torch.equal(actual,expected));self.assertEqual([x[0].shape[0] for x in b.calls],[2,2,1]);self.assertTrue(all(x[0].shape[1]==7 for x in b.calls));self.assertEqual(b.forward,old)
    def test_unknown_batch_tensor_is_rejected_and_restores(self):
        b=self.model();old=b.forward
        with self.assertRaisesRegex(ValueError,'unexpected'):
            with candidate_chunks(b,2):b(input_ids=torch.ones(2,3),attention_mask=torch.ones(2,3),position_ids=torch.ones(2,3),use_cache=False,return_dict=True)
        self.assertEqual(b.forward,old)
    def test_cache_refused(self):
        b=self.model()
        with self.assertRaisesRegex(ValueError,'protocol'):
            with candidate_chunks(b,2):b(input_ids=torch.ones(2,3),attention_mask=torch.ones(2,3),use_cache=True,return_dict=True)

if __name__=='__main__':unittest.main()
