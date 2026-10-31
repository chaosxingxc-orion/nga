"""Synthetic CPU counterexamples, never evidence of successful NPU recovery."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import torch

spec = importlib.util.spec_from_file_location('recompute',Path(__file__).with_name('r3_resume_recompute.py'))
R = importlib.util.module_from_spec(spec);spec.loader.exec_module(R)


class Recompute(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.pins={}
        (self.root/'CONTRACT.json').write_text(json.dumps({'source_step':100,'steps':20}))
        for name in ('replica_a','replica_b','replica_c','resumed','zero_moments','no_update'):
            root=self.root/name;(root/'ckpt').mkdir(parents=True)
            bad=name in ('zero_moments','no_update')
            rows=[dict(step=i,epoch=0,lr=.001,loss=2. if bad else 1.,grad_norm=1.,
                       base_questions=1,examples=1,tokens=10,chunks=1) for i in range(101,121)]
            (root/'losses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            path=root/'ckpt/step_000120.pt'
            torch.save({'step':120,'lora':{'weight':torch.tensor([2. if bad else 1.])},'sched':{'last_epoch':120}},path)
            self.pins[str(path)]='fixture'
        replicas=[dict(loss=0.,weight_relative_l2=0.) for _ in range(3)]
        resumed=dict(loss=0.,weight_relative_l2=0.)
        controls={n:dict(loss=1.,weight_relative_l2=1.) for n in ('zero_moments','no_update')}
        self.result={'replicas':replicas,'resumed':resumed,'controls':controls,
                     **R.numerical_verdict(replicas,resumed,controls)}
        (self.root/'CONTRACT_RESULT.json').write_text(json.dumps(self.result))

    def test_reconstructs_real_tensor_and_loss_distances(self):
        r=R.verify(self.root,self.pins)
        self.assertTrue(r['pass']);self.assertFalse(r['scientific_acceptance'])
        self.assertEqual(r['controls']['no_update']['weight_relative_l2'],1.)

    def test_claimed_pass_cannot_hide_changed_resumed_tensor(self):
        p=self.root/'resumed/ckpt/step_000120.pt'
        d=torch.load(p,weights_only=True);d['lora']['weight']+=.25;torch.save(d,p)
        with self.assertRaisesRegex(ValueError,'stored distance'):
            R.verify(self.root,self.pins)

    def test_shape_broadcast_nan_and_empty_inventory_refused(self):
        a={'step':120,'lora':{'w':torch.ones(2)}}
        rows=[{'loss':1.}]
        for weight in (torch.ones(1),torch.tensor([float('nan'),1.]),torch.ones(2,dtype=torch.float64)):
            with self.subTest(weight=weight),self.assertRaises(ValueError):
                R.distance(a,{'step':120,'lora':{'w':weight}},rows,rows,120)
        with self.assertRaises(ValueError):
            R.distance({'step':120,'lora':{}},{'step':120,'lora':{}},rows,rows,120)

    def test_duplicate_steps_and_changed_scheduler_refused(self):
        p=self.root/'resumed/losses.jsonl';raw=p.read_text();rows=raw.splitlines();rows[-1]=rows[0];p.write_text('\n'.join(rows)+'\n')
        with self.assertRaisesRegex(ValueError,'step population'):R.verify(self.root,self.pins)
        p.write_text(raw)
        p=self.root/'resumed/ckpt/step_000120.pt';d=torch.load(p,weights_only=True);d['sched']['last_epoch']=119;torch.save(d,p)
        with self.assertRaisesRegex(ValueError,'scheduler'):R.verify(self.root,self.pins)

    def test_controls_cannot_be_identical_to_reference(self):
        zero=dict(loss=0.,weight_relative_l2=0.)
        r=R.numerical_verdict([zero]*3,zero,{n:zero for n in ('zero_moments','no_update')})
        self.assertFalse(r['pass'])

    def test_nonfinite_overflow_and_boolean_distances_refused(self):
        zero=dict(loss=0.,weight_relative_l2=0.)
        for value in (float('nan'),float('inf'),-1.,True,1.7e308):
            with self.subTest(value=value),self.assertRaises(ValueError):
                R.numerical_verdict([dict(loss=value,weight_relative_l2=0.)]*3,zero,
                                    {n:zero for n in ('zero_moments','no_update')})


if __name__=='__main__':unittest.main()
